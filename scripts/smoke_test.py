#!/usr/bin/env python3
"""
End-to-End Smoke Test for Sports Hub Platform (Section 8 Quality Gate).
Covers:
  1. Health & OpenAPI Docs check
  2. Athlete registration & login + Organizer & Referee login
  3. Event eligibility failure (missing verified MEDICAL doc)
  4. Document Vault upload (MEDICAL) -> Organizer verification -> Eligibility passes
  5. Event registration -> Payment create-intent -> Mock completion -> CONFIRMED + Notification check
  6. Court booking with atomic lock -> Double-booking same court/slot returns HTTP 409
  7. OR-Tools CP-SAT Scheduler validation (8 teams / 2 courts & 6 teams / 3 courts) + assert zero court/team/rest conflicts + Commit schedule
  8. Injury AI RAG streaming query (NDJSON tokens + sources, works with or without Ollama)
  9. Native WebSocket (/ws/live) real-time score update broadcast verification
"""

import asyncio
import io
import json
import os
import socket
import subprocess
import sys
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import httpx
import websockets

BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000")
WS_URL = BASE_URL.replace("http://", "ws://").replace("https://", "wss://") + "/ws/live"


def log_step(step_num: int, title: str) -> None:
    print(f"\n[STEP {step_num}] {title}", flush=True)
    print("-" * 70, flush=True)


def verify_schedule_constraints(timetable: list, min_rest_slots: int) -> None:
    """Assert in code that no court or team conflicts exist and min_rest_slots is respected."""
    court_slot_usage = set()
    team_slots = defaultdict(list)

    for m in timetable:
        slot = m["slot_index"]
        court = m["court_number"]
        ta = m["team_a"]
        tb = m["team_b"]

        # 1. No court used by two matches in the same slot
        assert (slot, court) not in court_slot_usage, (
            f"Court conflict detected on court {court} at slot {slot}"
        )
        court_slot_usage.add((slot, court))

        # 2. No team plays twice in the same slot
        assert slot not in team_slots[ta], f"Team {ta} plays twice in slot {slot}"
        assert slot not in team_slots[tb], f"Team {tb} plays twice in slot {slot}"
        team_slots[ta].append(slot)
        team_slots[tb].append(slot)

    # 3. Minimum rest slots between any two matches of the same team
    for team, slots in team_slots.items():
        sorted_slots = sorted(slots)
        for i in range(len(sorted_slots) - 1):
            gap = sorted_slots[i + 1] - sorted_slots[i]
            assert gap >= (min_rest_slots + 1), (
                f"Rest constraint violated for {team}: slots {sorted_slots[i]} and {sorted_slots[i+1]} (gap={gap}, required>={min_rest_slots+1})"
            )


def ensure_backend_running():
    """If backend is not already listening on BASE_URL, spawn it on an available port for the test run."""
    global BASE_URL, WS_URL
    try:
        r = httpx.get(f"{BASE_URL}/health", timeout=2.0)
        if r.status_code == 200:
            return None
    except Exception:
        pass

    # Choose port 8000 if free, otherwise pick a free ephemeral port
    port = 8000
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
        except OSError:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]

    BASE_URL = f"http://127.0.0.1:{port}"
    WS_URL = f"ws://127.0.0.1:{port}/ws/live"

    backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
    print(f"Starting local FastAPI server on {BASE_URL} in {backend_dir} ...", flush=True)
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=backend_dir,
    )
    for _ in range(60):
        time.sleep(0.5)
        try:
            r = httpx.get(f"{BASE_URL}/health", timeout=1.5)
            if r.status_code == 200:
                return proc
        except Exception:
            continue
    proc.terminate()
    raise RuntimeError("Backend failed to start within 30 seconds.")


async def run_smoke_test() -> None:
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30.0) as client:
        # ------------------------------------------------------------------
        # 1. Health & Docs
        # ------------------------------------------------------------------
        log_step(1, "Checking /health and /docs endpoints")
        r_health = await client.get("/health")
        assert r_health.status_code == 200, f"Health check failed: {r_health.text}"
        r_docs = await client.get("/docs")
        assert r_docs.status_code == 200, "Swagger /docs did not return 200"
        print(f"PASS: /health -> {r_health.json()}", flush=True)
        print("PASS: /docs -> HTTP 200", flush=True)

        # ------------------------------------------------------------------
        # 2. Register & Login
        # ------------------------------------------------------------------
        log_step(2, "Registering new athlete & logging in Organizer / Referee")
        unique_email = f"smoke_{uuid.uuid4().hex[:8]}@demo.com"
        r_reg = await client.post(
            "/api/v1/auth/register",
            json={
                "name": "Smoke Test Athlete",
                "email": unique_email,
                "password": "Passw0rd!",
                "role": "athlete",
                "profile_metrics": {"height": 176, "weight": 70, "age": 21, "fitness_score": 88},
            },
        )
        assert r_reg.status_code == 201, f"Register failed: {r_reg.text}"
        athlete_token = r_reg.json()["access_token"]
        athlete_headers = {"Authorization": f"Bearer {athlete_token}"}

        # Also test login endpoint explicitly
        r_login = await client.post(
            "/api/v1/auth/login",
            json={"email": unique_email, "password": "Passw0rd!"},
        )
        assert r_login.status_code == 200
        print(f"PASS: Athlete registered & logged in ({unique_email})", flush=True)

        # Login seeded Organizer
        r_org = await client.post(
            "/api/v1/auth/login",
            json={"email": "organizer@demo.com", "password": "Passw0rd!"},
        )
        assert r_org.status_code == 200, f"Organizer login failed: {r_org.text}"
        org_token = r_org.json()["access_token"]
        org_headers = {"Authorization": f"Bearer {org_token}"}

        # Login seeded Referee
        r_ref = await client.post(
            "/api/v1/auth/login",
            json={"email": "referee@demo.com", "password": "Passw0rd!"},
        )
        assert r_ref.status_code == 200, f"Referee login failed: {r_ref.text}"
        ref_token = r_ref.json()["access_token"]
        ref_headers = {"Authorization": f"Bearer {ref_token}"}
        print("PASS: Organizer and Referee logged in", flush=True)

        # ------------------------------------------------------------------
        # 3. Create Event with ["MIN_AGE:18", "ID", "MEDICAL"] & Test Eligibility Fail -> Pass
        # ------------------------------------------------------------------
        log_step(3, "Testing Document Vault upload & Eligibility Engine (Fail -> Verify -> Pass)")
        future_dt = (datetime.now(timezone.utc) + timedelta(days=6)).replace(tzinfo=None).isoformat()
        r_ev = await client.post(
            "/api/v1/events",
            headers=org_headers,
            json={
                "sport_name": "Badminton",
                "title": "Smoke Test Super Series",
                "venue": "Main Indoor Arena",
                "date_time": future_dt,
                "entry_fee": 50000,
                "capacity": 16,
                "mandatory_requirements": ["MIN_AGE:18", "ID", "MEDICAL"],
            },
        )
        assert r_ev.status_code == 201, f"Create event failed: {r_ev.text}"
        event_id = r_ev.json()["id"]

        # Check eligibility BEFORE uploading docs -> must be False
        r_elig1 = await client.get(f"/api/v1/events/{event_id}/eligibility", headers=athlete_headers)
        assert r_elig1.status_code == 200
        elig1 = r_elig1.json()
        assert elig1["eligible"] is False, "Expected athlete without docs to be ineligible"
        print(f"PASS: Initial eligibility is False ({len(elig1['checks'])} checks evaluated)", flush=True)

        # Attempt registration while ineligible -> must return 422
        r_reg_fail = await client.post(f"/api/v1/events/{event_id}/register", headers=athlete_headers)
        assert r_reg_fail.status_code == 422, f"Expected 422 when ineligible, got {r_reg_fail.status_code}"
        print("PASS: Registration blocked with HTTP 422 when ineligible", flush=True)

        # Upload ID and MEDICAL documents
        doc_ids = []
        for dtype in ("ID", "MEDICAL"):
            files = {"file": (f"{dtype.lower()}.pdf", io.BytesIO(b"%PDF-1.4 mock document content"), "application/pdf")}
            r_up = await client.post(
                "/api/v1/vault/documents",
                headers=athlete_headers,
                data={"doc_type": dtype},
                files=files,
            )
            assert r_up.status_code == 201, f"Upload {dtype} failed: {r_up.text}"
            doc_ids.append(r_up.json()["id"])

        # Still unverified -> eligibility must still be False
        r_elig_pending = await client.get(f"/api/v1/events/{event_id}/eligibility", headers=athlete_headers)
        assert r_elig_pending.json()["eligible"] is False

        # Organizer verifies both documents
        for did in doc_ids:
            r_ver = await client.post(f"/api/v1/vault/documents/{did}/verify", headers=org_headers)
            assert r_ver.status_code == 200
            assert r_ver.json()["is_verified"] is True

        # Now eligibility must be True!
        r_elig2 = await client.get(f"/api/v1/events/{event_id}/eligibility", headers=athlete_headers)
        assert r_elig2.status_code == 200
        assert r_elig2.json()["eligible"] is True, f"Expected eligible=True after verification: {r_elig2.json()}"
        print("PASS: Eligibility transitioned to True after Organizer verified ID & MEDICAL documents", flush=True)

        # ------------------------------------------------------------------
        # 4. Register for Event -> Create Payment Intent -> Mock Complete -> Notification
        # ------------------------------------------------------------------
        log_step(4, "Registering for Event, Creating Payment Intent & Completing Mock Payment")
        r_ev_reg = await client.post(f"/api/v1/events/{event_id}/register", headers=athlete_headers)
        assert r_ev_reg.status_code == 201, f"Event registration failed: {r_ev_reg.text}"
        reg_data = r_ev_reg.json()
        assert reg_data["status"] == "PENDING_PAYMENT"
        registration_id = reg_data["id"]

        r_intent = await client.post(
            "/api/v1/payments/create-intent",
            headers=athlete_headers,
            json={"purpose": "REGISTRATION", "ref_id": registration_id, "gateway": "stripe"},
        )
        assert r_intent.status_code == 201, f"Create payment intent failed: {r_intent.text}"
        payment_id = r_intent.json()["payment_id"]

        r_pay_complete = await client.post(
            f"/api/v1/payments/mock/complete/{payment_id}",
            headers=athlete_headers,
        )
        assert r_pay_complete.status_code == 200
        assert r_pay_complete.json()["status"] == "SUCCESS"

        # Verify registration status is CONFIRMED
        r_my_regs = await client.get("/api/v1/events/registrations/me", headers=athlete_headers)
        assert r_my_regs.status_code == 200
        confirmed_reg = next(r for r in r_my_regs.json() if r["id"] == registration_id)
        assert confirmed_reg["status"] == "CONFIRMED"

        # Verify notification exists
        r_notifs = await client.get("/api/v1/notifications/me", headers=athlete_headers)
        assert r_notifs.status_code == 200
        notifs = r_notifs.json()
        assert any(n["kind"] == "REGISTRATION_CONFIRMED" for n in notifs), "Missing REGISTRATION_CONFIRMED notification"
        print("PASS: Registration CONFIRMED and REGISTRATION_CONFIRMED notification delivered", flush=True)

        # ------------------------------------------------------------------
        # 5. Court Booking & Double-Booking 409 Verification
        # ------------------------------------------------------------------
        log_step(5, "Testing Court Booking & Atomic Lock Double-Booking Rejection (HTTP 409)")
        r_courts = await client.get("/api/v1/courts")
        assert r_courts.status_code == 200
        court_id = r_courts.json()[0]["id"]

        slot_dt = (datetime.now(timezone.utc) + timedelta(days=3)).replace(
            hour=10, minute=0, second=0, microsecond=0, tzinfo=None
        )
        r_book1 = await client.post(
            "/api/v1/bookings",
            headers=athlete_headers,
            json={"court_id": court_id, "slot_start": slot_dt.isoformat()},
        )
        assert r_book1.status_code == 201, f"First court booking failed: {r_book1.text}"

        # Second booking on same court + slot must fail with 409 Conflict
        r_book2 = await client.post(
            "/api/v1/bookings",
            headers=org_headers,
            json={"court_id": court_id, "slot_start": slot_dt.isoformat()},
        )
        assert r_book2.status_code == 409, f"Expected 409 Conflict on double booking, got {r_book2.status_code}"
        print("PASS: First booking succeeded (201) and concurrent double-booking rejected with HTTP 409", flush=True)

        # ------------------------------------------------------------------
        # 6. OR-Tools CP-SAT Scheduler (8 teams / 2 courts & 6 teams / 3 courts)
        # ------------------------------------------------------------------
        log_step(6, "Testing Google OR-Tools CP-SAT Tournament Scheduler & Conflict Assertions")
        # Case A: 8 teams, 2 courts, single_elimination
        teams_8 = [f"Team {i}" for i in range(1, 9)]
        r_sched_8 = await client.post(
            "/api/v1/scheduler/generate",
            json={
                "teams": teams_8,
                "num_courts": 2,
                "match_duration_minutes": 60,
                "start_time": future_dt,
                "min_rest_slots": 1,
                "format": "single_elimination",
            },
        )
        assert r_sched_8.status_code == 200, f"8-team schedule failed: {r_sched_8.text}"
        sched_8 = r_sched_8.json()
        verify_schedule_constraints(sched_8["timetable"], min_rest_slots=1)
        print(
            f"PASS: 8 teams / 2 courts (single_elimination) -> {sched_8['total_matches']} matches across {sched_8['makespan_slots']} slots ({sched_8['solver_status']})",
            flush=True,
        )

        # Case B: 6 teams, 3 courts, round_robin (15 matches) + commit to DB
        teams_6 = ["Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot"]
        r_sched_6 = await client.post(
            f"/api/v1/scheduler/generate/{event_id}/commit",
            headers=org_headers,
            json={
                "teams": teams_6,
                "num_courts": 3,
                "match_duration_minutes": 45,
                "start_time": future_dt,
                "min_rest_slots": 1,
                "format": "round_robin",
            },
        )
        assert r_sched_6.status_code == 201, f"6-team round_robin commit failed: {r_sched_6.text}"
        committed_matches = r_sched_6.json()
        assert len(committed_matches) == 15
        print(f"PASS: 6 teams / 3 courts (round_robin) -> {len(committed_matches)} matches committed to DB", flush=True)

        # ------------------------------------------------------------------
        # 7. Injury AI Assistant RAG Streaming Query
        # ------------------------------------------------------------------
        log_step(7, "Testing Injury AI Assistant RAG Streaming Endpoint (/api/v1/injury/query)")
        r_inj_health = await client.get("/api/v1/injury/health")
        assert r_inj_health.status_code == 200
        print(f"Injury AI Health: {r_inj_health.json()}", flush=True)

        tokens_collected = []
        sources_collected = []
        async with client.stream(
            "POST",
            "/api/v1/injury/query",
            json={
                "question": "How should I manage an acute lateral ankle sprain and when do I need an X-ray?",
                "sport": "Badminton",
                "history": "Rolled ankle landing from an overhead smash",
            },
        ) as stream_resp:
            assert stream_resp.status_code == 200
            async for line in stream_resp.aiter_lines():
                if not line.strip():
                    continue
                obj = json.loads(line)
                if "token" in obj:
                    tokens_collected.append(obj["token"])
                if obj.get("done"):
                    sources_collected = obj.get("sources", [])

        full_answer = "".join(tokens_collected)
        assert len(full_answer) > 50, "Injury AI answer was unexpectedly empty"
        assert len(sources_collected) > 0, "Injury AI did not return any RAG sources"
        print(
            f"PASS: Streamed {len(full_answer)} chars with {len(sources_collected)} RAG sources ({[s['source'] for s in sources_collected]})",
            flush=True,
        )

        # ------------------------------------------------------------------
        # 8. Live Scores WebSocket Broadcast
        # ------------------------------------------------------------------
        log_step(8, "Testing Real-Time WebSocket (/ws/live) Score Update Broadcast")
        r_matches = await client.get("/api/v1/live/matches")
        assert r_matches.status_code == 200
        target_match = r_matches.json()[0]
        match_id = target_match["id"]

        async with websockets.connect(WS_URL) as ws:
            # First message is CONNECTED greeting
            greeting = json.loads(await asyncio.wait_for(ws.recv(), timeout=5.0))
            assert greeting.get("type") == "CONNECTED"

            # Referee updates score via REST PUT
            r_score = await client.put(
                f"/api/v1/live/matches/{match_id}/score",
                headers=ref_headers,
                json={"score_a": 21, "score_b": 19, "status": "LIVE"},
            )
            assert r_score.status_code == 200

            # WebSocket must immediately receive the broadcast
            ws_event = json.loads(await asyncio.wait_for(ws.recv(), timeout=5.0))
            assert ws_event.get("type") == "SCORE_UPDATE"
            assert ws_event["match"]["id"] == match_id
            assert ws_event["match"]["score_a"] == 21
            assert ws_event["match"]["score_b"] == 19
            print(
                f"PASS: WebSocket received real-time SCORE_UPDATE -> {ws_event['match']['team_a']} {ws_event['match']['score_a']} - {ws_event['match']['score_b']} {ws_event['match']['team_b']}",
                flush=True,
            )

    print("\n" + "=" * 70, flush=True)
    print("ALL 8 END-TO-END SMOKE TEST SUITES PASSED SUCCESSFULLY!", flush=True)
    print("=" * 70, flush=True)


if __name__ == "__main__":
    spawned_proc = None
    try:
        spawned_proc = ensure_backend_running()
        asyncio.run(run_smoke_test())
    except Exception as exc:
        print(f"\nSMOKE TEST FAILED: {exc}", file=sys.stderr, flush=True)
        sys.exit(1)
    finally:
        if spawned_proc is not None:
            spawned_proc.terminate()
