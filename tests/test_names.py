from sim import roster
from sim.rng import streams

SEEDS = range(0, 600)


def test_blocklist_catches_known_real_names() -> None:
    assert roster.is_real_club("Arsenal")
    assert roster.is_real_club("Salford Rovers")  # real town
    assert roster.is_real_town("Aston")  # first word of a real club
    assert roster.is_real_surname("Haaland")
    assert roster.is_real_surname("de bruyne")
    assert not roster.is_real_club("Linbridge Harriers")


def test_generated_names_are_not_real() -> None:
    bl = roster.blocklist()
    for seed in SEEDS:
        home, away, venue = roster.build(streams(seed).roster)
        assert not roster.is_real_town(venue.split()[0]), venue
        for sheet in (home, away):
            assert not roster.is_real_club(sheet.team.name), sheet.team.name
            for p in sheet.players:
                _, last = p.name.split(" ", 1)
                assert not roster.is_real_surname(last), p.name
                assert p.name.lower() not in bl["surnames"], p.name


def test_rosters_are_well_formed() -> None:
    for seed in range(50):
        home, away, _ = roster.build(streams(seed).roster)
        assert home.team.team_id != away.team.team_id
        assert home.team.colors[0] != away.team.colors[0]
        for sheet in (home, away):
            shirts = [p.shirt for p in sheet.players]
            assert len(set(shirts)) == len(shirts) == 16
            assert sum(p.starter for p in sheet.players) == 11
            assert [p.position for p in sheet.players].count("GK") == 2
