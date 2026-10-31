from datetime import datetime, timedelta
from app.schemas import SchedulerGenerateRequest
from app.services.scheduler.solver import solve_tournament_schedule


def test_scheduler_8_teams_2_courts():
    req = SchedulerGenerateRequest(
        teams=[f"Team {i}" for i in range(1, 9)],
        num_courts=2,
        match_duration_minutes=60,
        start_time=datetime(2026, 11, 10, 9, 0, 0),
        min_rest_slots=1,
        format="single_elimination",
    )
    res = solve_tournament_schedule(req)
    assert res.total_matches == 4
    assert len(res.timetable) == 4


def test_scheduler_6_teams_3_courts_round_robin():
    req = SchedulerGenerateRequest(
        teams=["T1", "T2", "T3", "T4", "T5", "T6"],
        num_courts=3,
        match_duration_minutes=60,
        start_time=datetime(2026, 11, 10, 9, 0, 0),
        min_rest_slots=1,
        format="round_robin",
    )
    res = solve_tournament_schedule(req)
    assert res.total_matches == 15
    assert len(res.timetable) == 15
    # Verify no two matches share (slot_index, court_number)
    used = {(m.slot_index, m.court_number) for m in res.timetable}
    assert len(used) == 15

