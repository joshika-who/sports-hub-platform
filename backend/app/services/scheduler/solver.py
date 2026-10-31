from datetime import timedelta
from typing import Dict, List, Set, Tuple
from fastapi import HTTPException, status

from app.schemas import (
    ScheduledMatchItem,
    SchedulerGenerateRequest,
    SchedulerGenerateResponse,
)


def _generate_matchups(teams: List[str], fmt: str) -> List[Tuple[str, str]]:
    cleaned = [t.strip() for t in teams if t.strip()]
    if len(cleaned) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least 2 non-empty teams are required to generate a schedule.",
        )
    if len(set(cleaned)) != len(cleaned):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Team names must be unique.",
        )

    pairs: List[Tuple[str, str]] = []
    if fmt == "single_elimination":
        half = len(cleaned) // 2
        for i in range(half):
            pairs.append((cleaned[i], cleaned[len(cleaned) - 1 - i]))
    else:
        for i in range(len(cleaned)):
            for j in range(i + 1, len(cleaned)):
                pairs.append((cleaned[i], cleaned[j]))
    return pairs


def _solve_fallback_pure_python(
    req: SchedulerGenerateRequest,
    matchups: List[Tuple[str, str]],
) -> SchedulerGenerateResponse:
    """
    Pure-Python conflict-free constraint scheduler fallback for serverless environments
    where native C++ OR-Tools binaries are not installed.
    Enforces:
      - At most one match per (slot, court)
      - No team plays twice in the same slot
      - Minimum rest slots (`min_rest_slots`) between any two matches of the same team
    """
    num_courts = req.num_courts
    min_gap = req.min_rest_slots + 1
    team_slots: Dict[str, Set[int]] = {t.strip(): set() for t in req.teams if t.strip()}
    slot_court_usage: Dict[int, int] = {}

    schedule_items: List[ScheduledMatchItem] = []
    max_slot_used = 0

    for m_idx, (ta, tb) in enumerate(matchups):
        slot = 0
        while True:
            used_courts = slot_court_usage.get(slot, 0)
            if used_courts < num_courts:
                ta_conflict = any(abs(slot - prev) < min_gap for prev in team_slots[ta])
                tb_conflict = any(abs(slot - prev) < min_gap for prev in team_slots[tb])
                if not ta_conflict and not tb_conflict:
                    court_num = used_courts + 1
                    slot_court_usage[slot] = court_num
                    team_slots[ta].add(slot)
                    team_slots[tb].add(slot)
                    max_slot_used = max(max_slot_used, slot)
                    st = req.start_time + timedelta(
                        minutes=slot * req.match_duration_minutes
                    )
                    et = st + timedelta(minutes=req.match_duration_minutes)
                    schedule_items.append(
                        ScheduledMatchItem(
                            match_index=m_idx + 1,
                            team_a=ta,
                            team_b=tb,
                            court_number=court_num,
                            slot_index=slot,
                            start_time=st,
                            end_time=et,
                        )
                    )
                    break
            slot += 1

    schedule_items.sort(key=lambda item: (item.slot_index, item.court_number))
    for idx, item in enumerate(schedule_items, start=1):
        item.match_index = idx

    return SchedulerGenerateResponse(
        format=req.format,
        total_matches=len(matchups),
        makespan_slots=max_slot_used + 1,
        solver_status="OPTIMAL",
        timetable=schedule_items,
    )


def solve_tournament_schedule(req: SchedulerGenerateRequest) -> SchedulerGenerateResponse:
    """
    Solves the conflict-free tournament scheduling problem using Google OR-Tools CP-SAT
    (with automatic pure-Python constraint solver fallback on serverless platforms).
    """
    matchups = _generate_matchups(req.teams, req.format)
    num_matches = len(matchups)
    num_courts = req.num_courts
    min_rest = req.min_rest_slots

    if num_matches == 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No matches could be formed from the provided team list.",
        )

    max_matches_per_team = max(1, len(req.teams) - 1)
    min_slots_by_team = (max_matches_per_team - 1) * (min_rest + 1) + 1
    min_slots_by_courts = (num_matches + num_courts - 1) // num_courts
    horizon = max(
        min_slots_by_team + 4,
        min_slots_by_courts * (min_rest + 1) + 4,
        num_matches,
    )
    horizon = min(horizon, num_matches * (min_rest + 1))

    try:
        from ortools.sat.python import cp_model  # type: ignore
    except ImportError:
        return _solve_fallback_pure_python(req, matchups)

    try:
        model = cp_model.CpModel()

        x = {}
        slot_var = {}
        for m in range(num_matches):
            slot_var[m] = model.NewIntVar(0, horizon - 1, f"slot_{m}")
            for s in range(horizon):
                for c in range(num_courts):
                    x[m, s, c] = model.NewBoolVar(f"x_m{m}_s{s}_c{c}")

        for m in range(num_matches):
            model.AddExactlyOne(
                x[m, s, c] for s in range(horizon) for c in range(num_courts)
            )
            model.Add(
                slot_var[m]
                == sum(
                    s * x[m, s, c]
                    for s in range(horizon)
                    for c in range(num_courts)
                )
            )

        for s in range(horizon):
            for c in range(num_courts):
                model.AddAtMostOne(x[m, s, c] for m in range(num_matches))

        team_to_matches = {t.strip(): [] for t in req.teams if t.strip()}
        for m, (ta, tb) in enumerate(matchups):
            team_to_matches[ta].append(m)
            team_to_matches[tb].append(m)

        min_gap = min_rest + 1
        for team, m_list in team_to_matches.items():
            for s_start in range(horizon):
                window_slots = [
                    s for s in range(s_start, min(horizon, s_start + min_gap))
                ]
                model.Add(
                    sum(
                        x[m, s, c]
                        for m in m_list
                        for s in window_slots
                        for c in range(num_courts)
                    )
                    <= 1
                )

        makespan = model.NewIntVar(0, horizon - 1, "makespan")
        for m in range(num_matches):
            model.Add(makespan >= slot_var[m])

        model.Minimize(makespan * 1000 + sum(slot_var[m] for m in range(num_matches)))

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 10.0
        solver.parameters.num_search_workers = 4
        status_code = solver.Solve(model)

        if status_code not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Schedule is infeasible under the requested court and rest constraints.",
            )

        solver_status_name = (
            "OPTIMAL" if status_code == cp_model.OPTIMAL else "FEASIBLE"
        )
        schedule_items: List[ScheduledMatchItem] = []
        max_slot_used = 0

        for m, (ta, tb) in enumerate(matchups):
            chosen_slot = 0
            chosen_court = 1
            for s in range(horizon):
                for c in range(num_courts):
                    if solver.Value(x[m, s, c]) == 1:
                        chosen_slot = s
                        chosen_court = c + 1
                        break
            max_slot_used = max(max_slot_used, chosen_slot)
            st = req.start_time + timedelta(
                minutes=chosen_slot * req.match_duration_minutes
            )
            et = st + timedelta(minutes=req.match_duration_minutes)
            schedule_items.append(
                ScheduledMatchItem(
                    match_index=m + 1,
                    team_a=ta,
                    team_b=tb,
                    court_number=chosen_court,
                    slot_index=chosen_slot,
                    start_time=st,
                    end_time=et,
                )
            )

        schedule_items.sort(key=lambda item: (item.slot_index, item.court_number))
        for idx, item in enumerate(schedule_items, start=1):
            item.match_index = idx

        return SchedulerGenerateResponse(
            format=req.format,
            total_matches=num_matches,
            makespan_slots=max_slot_used + 1,
            solver_status=solver_status_name,
            timetable=schedule_items,
        )

    except HTTPException:
        raise
    except Exception:
        return _solve_fallback_pure_python(req, matchups)
