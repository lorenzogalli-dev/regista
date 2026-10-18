import itertools

from sim import roster, storylines
from sim.generate import simulate
from sim.rng import streams
from sim.seeds import (
    CALIBRATION_CONTROL_SEEDS,
    CALIBRATION_SEEDS,
    CONTROL_SEEDS,
    DEV_SEEDS,
    EVAL_SEEDS,
    SIGNAL_HOLDOUT_SEEDS,
    SIGNAL_JUDGE_SEEDS,
    is_control,
)
from sim.storylines import MIN

PERIOD_ENDS = [47 * MIN, 95 * MIN]


def _plan(
    seed: int, control: bool = False, pool: tuple = storylines.ACTIVE_TYPES
) -> storylines.Modifiers:
    rs = streams(seed)
    home, away, _ = roster.build(rs.roster)
    return storylines.plan(rs.storylines, home, away, PERIOD_ENDS, control, pool)


def test_seed_sets_are_disjoint() -> None:
    sets = [
        DEV_SEEDS,
        EVAL_SEEDS,
        CONTROL_SEEDS,
        CALIBRATION_SEEDS,
        CALIBRATION_CONTROL_SEEDS,
        SIGNAL_JUDGE_SEEDS,
        SIGNAL_HOLDOUT_SEEDS,
    ]
    for i, a in enumerate(sets):
        for b in sets[i + 1 :]:
            assert not set(a) & set(b)
    assert all(is_control(s) for s in SIGNAL_HOLDOUT_SEEDS)
    assert not any(is_control(s) for s in SIGNAL_JUDGE_SEEDS)


def test_two_or_three_non_overlapping_windows_inside_a_period() -> None:
    seen_types = set()
    for seed in range(200):
        plans = _plan(seed).plans
        assert 2 <= len(plans) <= 3
        wins = sorted((p.sl.start_ms, p.sl.end_ms) for p in plans)
        for (_, e1), (s2, _) in itertools.pairwise(wins):
            assert s2 >= e1 + 4 * MIN
        for s, e in wins:
            assert (s >= 0 and e <= PERIOD_ENDS[0]) or (s >= PERIOD_ENDS[0] and e <= PERIOD_ENDS[1])
        seen_types |= {p.sl.type for p in plans}
    assert seen_types == set(storylines.ACTIVE_TYPES)


def test_control_has_no_storylines() -> None:
    assert _plan(9000, control=True).plans == []


def test_modifiers_only_inside_window() -> None:
    for seed in range(100):
        mods = _plan(seed, pool=storylines.TYPES)  # pressing_spell is disabled by default
        for p in mods.plans:
            if p.sl.type != "pressing_spell":
                continue
            before, inside, after = p.sl.start_ms - MIN, p.sl.start_ms + MIN, p.sl.end_ms + MIN
            assert mods.press(p.side, 0.5, inside) == 0.97
            others = [q for q in mods.plans if q is not p and q.sl.type == "momentum_shift"]
            if not others:
                assert mods.press(p.side, 0.5, before) == 0.5
                assert mods.press(p.side, 0.5, after) == 0.5


def test_disabled_types_are_not_generated() -> None:
    for seed in range(200):
        assert {p.sl.type for p in _plan(seed).plans} <= set(storylines.ACTIVE_TYPES)


def test_every_storyline_has_signals_and_explanation() -> None:
    for seed in range(100):
        for p in _plan(seed, pool=storylines.TYPES).plans:
            assert p.sl.expected_signals
            assert p.sl.canonical_explanation
            assert p.sl.end_ms > p.sl.start_ms


def test_forced_events_happen_in_the_match() -> None:
    """momentum_shift triggers and fatigue_drop substitutions appear in the event log.

    Scheduled actions wait for the ball to land, so they may fire a few seconds late.
    """
    checked = 0
    for seed in DEV_SEEDS:
        mods = _plan(seed)
        kinds = {p.sl.type for p in mods.plans}
        if not kinds & {"momentum_shift", "fatigue_drop"}:
            continue
        result, gt = simulate(seed)
        for sl in gt.storylines:
            at = [e for e in result.events if 0 <= e["t_ms"] - sl.start_ms <= 10_000]
            if sl.type == "momentum_shift" and sl.variant == "red_card":
                assert any(
                    e["type"] == "card" and e["outcome"] == "red" and e["player_id"] == sl.actors[0]
                    for e in at
                ), sl
            if sl.type == "momentum_shift" and sl.variant == "sub":
                assert any(
                    e["type"] == "sub" and e["qualifiers"]["player_in"] == sl.actors[0] for e in at
                ), sl
            if sl.type == "fatigue_drop":
                end = [
                    e
                    for e in result.events
                    if 0 <= e["t_ms"] - sl.end_ms <= 10_000 and e["type"] == "sub"
                ]
                assert any(e["qualifiers"]["player_out"] == sl.actors[0] for e in end), sl
        checked += 1
        if checked >= 3:
            break
    assert checked >= 1
