import itertools

from sim import io
from sim.schema import PITCH_LENGTH, PITCH_WIDTH, TICK_MS, Event, MatchMeta


def test_meta_and_events_validate(sample_dirs) -> None:
    out, _ = sample_dirs
    meta = io.read_meta(out)
    assert MatchMeta.model_validate(meta.model_dump()) == meta
    events = [Event.model_validate(e) for e in io.iter_events(out)]
    assert events, "no events"
    ts = [e.t_ms for e in events]
    assert ts == sorted(ts), "events are not time-ordered"
    ids = [int(e.event_id[2:]) for e in events]
    assert ids == list(range(1, len(ids) + 1))
    pids = [e.possession_id for e in events]
    assert all(b >= a for a, b in itertools.pairwise(pids)), "possession_id decreased"


def test_event_types_cover_spec(sample) -> None:
    types = {e["type"] for e in sample[0].events}
    for t in (
        "kickoff",
        "pass",
        "carry",
        "shot",
        "tackle",
        "pressure",
        "possession_change",
        "period_start",
        "period_end",
        "sub",
    ):
        assert t in types, t


def test_events_on_pitch(sample) -> None:
    for e in sample[0].events:
        assert -3 <= e["x"] <= PITCH_LENGTH + 3 and -3 <= e["y"] <= PITCH_WIDTH + 3, e


def test_pass_and_shot_speeds_in_range(sample) -> None:
    for e in sample[0].events:
        if e["type"] == "pass":
            assert 8.0 <= e["qualifiers"]["ball_speed_ms"] <= 25.0
        if e["type"] == "shot":
            assert 15.0 <= e["qualifiers"]["ball_speed_ms"] <= 35.0


def test_tracking_is_10hz_and_complete(sample_dirs, sample) -> None:
    out, _ = sample_dirs
    meta = io.read_meta(out)
    frames = list(itertools.islice(io.iter_tracking(out), 50))
    assert [f["t_ms"] for f in frames] == [i * TICK_MS for i in range(50)]
    assert len(frames[0]["players"]) == 22
    assert len(sample[0].t_ms) == meta.period_end_ms[-1] // TICK_MS
    assert set(frames[0]["ball"]) == {"x", "y", "z", "speed_ms"}


def test_stoppage_time_one_to_four_minutes(sample) -> None:
    p1, p2 = sample[0].meta.period_end_ms
    assert 46 * 60_000 <= p1 <= 49 * 60_000
    assert 46 * 60_000 <= p2 - p1 <= 49 * 60_000
