from eval.score import matches, on_air

SL = {
    "type": "pressing_spell",
    "team_id": "t_a",
    "start_ms": 600_000,
    "end_ms": 1_500_000,
    "actors": [],
}


def moment(t_end: int, tag: str, team: str = "t_a", salience: int = 3, score: float = 2.0) -> dict:
    return {
        "status": "approved",
        "candidate": {
            "t_ms": t_end,
            "window_start_ms": t_end - 900_000,
            "window_end_ms": t_end,
            "score": score,
        },
        "detector": {"salience": salience},
        "explanation": {"mechanism_tag": tag, "team_id": team, "player_ids": [], "evidence": []},
    }


def test_match_uses_window_midpoint_and_strict_uses_emission_time() -> None:
    late = moment(1_800_000, "pressing_spell")  # window 15-30 min, midpoint 22.5 min
    assert matches(late, SL)
    assert not matches(late, SL, strict=True)  # emitted at 30 min > 25 + 3
    assert not matches(moment(1_800_000, "momentum_shift"), SL)
    assert not matches(moment(1_800_000, "pressing_spell", team="t_b"), SL)


def test_on_air_takes_three_highest_salience() -> None:
    ms = [moment(1_000_000 + i, "none", salience=s, score=i) for i, s in enumerate([2, 5, 3, 5, 1])]
    top = on_air(ms)
    assert [m["detector"]["salience"] for m in top] == [5, 5, 3]
    assert top[0]["candidate"]["score"] > top[1]["candidate"]["score"]
