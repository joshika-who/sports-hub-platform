from datetime import datetime, timedelta
from typing import List, Tuple
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
        # First-round bracket pairings (1 vs N, 2 vs N-1, etc.)
        half = len(cleaned) // 2
        for i in range(half):
            pairs.append((cleaned[i], cleaned[len(cleaned) - 1 - i]))
    else:
        # Round-robin: every team plays every other team once
        for i in range(len(cleaned)):
            for j in range(i + 1, len(cleaned)):
                pairs.append((cleaned[i], cleaned[j]))
    return pairs


def solve_tournament_schedule(req: SchedulerGenerateRequest) -> SchedulerGenerateResponse:
    """
    Solves the conflict-free tournament scheduling problem using Google OR-Tools CP-SAT.
    Hard Constraints:
      1. Each match is assigned to exactly one (slot, court).
      2. At most one match per (slot, court).
      3. No team plays more than one match in the same slot.
      4. Minimum rest slots (`min_rest_slots`) enforced between any two matches of the same team.
    Objective:
      Minimize total makespan (last slot used), with secondary preference for earlier compact slots.
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

    # Upper bound on slots needed: worst-case sequential with min_rest spacing
    max_matches_per_team = max(1, len(req.teams) - 1)
    min_slots_by_team = (max_matches_per_team - 1) * (min_rest + 1) + 1
    min_slots_by_courts = (num_matches + num_courts - 1) // num_courts
    horizon = max(min_slots_by_team + 4, min_slots_by_courts * (min_rest + 1) + 4, num_matches)
    # Cap horizon to keep CP-SAT variable count fast while still generous
    horizon = min(horizon, num_matches * (min_rest + 1))

    try:
        from ortools.sat.python import cp_model  # type: ignore

        model = cp_model.CpModel()

        # x[m, s, c] == 1 iff match m is scheduled at slot s on court c
        x = {}
        slot_var = {}
        for m in range(num_matches):
            slot_var[m] = model.NewIntVar(0, horizon - 1, f"slot_{m}")
            for s in range(horizon):
                for c in range(num_courts):
                    x[m, s, c] = model.NewBoolVar(f"x_m{m}_s{s}_c{c}")

        # 1. Each match happens in exactly one (slot, court), and link slot_var[m]
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

        # 2. No court used by two matches in one slot
        for s in range(horizon):
            for c in range(num_courts):
                model.AddAtMostOne(x[m, s, c] for m in range(num_matches))

        # 3 & 4. Team non-overlap and minimum rest between a team's matches
        team_to_matches = {t.strip(): [] for t in req.teams if t.strip()}
        for m, (ta, tb) in enumerate(matchups):
            team_to_matches[ta].append(m)
            team_to_matches[tb].append(m)

        min_gap = min_rest + 1  # |slot(m1) - slot(m2)| >= min_rest + 1
        for team, m_list in team_to_matches.items():
            # For each slot window of length `min_gap`, team can play at most 1 match
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

        # Objective: Minimize makespan * 1000 + sum(slot_var) for compact, balanced schedules
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
            st = req.start_time + timedelta(minutes=chosen_slot * req.match_duration_minutes)
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
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Constraint solver error: {exc}",
        )

