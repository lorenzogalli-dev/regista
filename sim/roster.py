"""Fictional clubs, venues and players.

Names are assembled from invented syllables and checked against a blocklist of real
footballers, clubs and towns (sim/real_names_blocklist.txt).
"""

from dataclasses import dataclass
from functools import cache
from pathlib import Path

import numpy as np

from sim.schema import Player, PlayerAttrs, Team, TeamStyle

BLOCKLIST_PATH = Path(__file__).with_name("real_names_blocklist.txt")

TOWN_START = (
    "Har",
    "Bel",
    "Cor",
    "Dun",
    "Thorn",
    "Kel",
    "Elm",
    "Fen",
    "Gal",
    "Hol",
    "Lin",
    "Mor",
    "Pen",
    "Quar",
    "Ros",
    "Tam",
    "Ver",
    "Wil",
    "Yar",
    "Ald",
    "Brin",
    "Cal",
    "Dra",
    "Esk",
    "Glen",
    "Hart",
    "Ivy",
    "Oak",
    "Ash",
    "Sel",
)
TOWN_END = (
    "mouth",
    "ford",
    "wick",
    "stead",
    "haven",
    "more",
    "dale",
    "port",
    "field",
    "holm",
    "cliff",
    "bridge",
    "combe",
    "hurst",
    "gate",
)
CLUB_SUFFIX = (
    "Rovers",
    "Athletic",
    "Wanderers",
    "Albion",
    "Town",
    "Harriers",
    "Mariners",
    "Rangers",
    "Borough",
    "Vale",
)
VENUE_SUFFIX = ("Park", "Ground", "Lane", "Road", "Meadow", "Arena")

FIRST_NAMES = (
    "Teo",
    "Ari",
    "Nico",
    "Luca",
    "Milo",
    "Ezra",
    "Jonah",
    "Remy",
    "Silas",
    "Otto",
    "Felix",
    "Rafa",
    "Idris",
    "Kofi",
    "Tomas",
    "Bram",
    "Emil",
    "Soren",
    "Malik",
    "Dario",
    "Yusuf",
    "Mateo",
    "Ilan",
    "Joel",
    "Kai",
    "Leon",
    "Noel",
    "Omar",
    "Pavel",
    "Ruben",
    "Sami",
    "Tobi",
    "Viktor",
    "Wes",
    "Zeke",
    "Anders",
    "Bastian",
    "Caio",
    "Dmitri",
    "Elio",
    "Florin",
    "Gael",
    "Hugo",
    "Ivo",
    "Jarek",
    "Kian",
    "Lior",
    "Marek",
    "Nils",
    "Oren",
    "Piet",
    "Quentin",
    "Rasmus",
    "Stellan",
    "Tiago",
    "Ugo",
    "Vito",
    "Wim",
    "Yannick",
    "Zoran",
)
SURNAME_START = (
    "Al",
    "Bra",
    "Cor",
    "Dal",
    "Ev",
    "Fen",
    "Gar",
    "Hal",
    "Ir",
    "Jas",
    "Kel",
    "Lor",
    "Mar",
    "Nor",
    "Os",
    "Pel",
    "Quin",
    "Ral",
    "Sev",
    "Tor",
    "Ul",
    "Var",
    "Wes",
    "Yor",
    "Zan",
    "Bel",
    "Cal",
    "Dor",
    "Ell",
    "Fal",
    "Mor",
    "Tal",
)
SURNAME_END = (
    "ton",
    "vik",
    "dell",
    "more",
    "sen",
    "ard",
    "ley",
    "win",
    "rick",
    "ston",
    "ner",
    "vell",
    "berg",
    "ani",
    "ovic",
    "ini",
    "ens",
    "ham",
    "dor",
    "oux",
    "ak",
    "ssen",
    "low",
)

COLOR_PAIRS = (
    ("#0B3D91", "#FFFFFF"),
    ("#B3122E", "#F4E9D8"),
    ("#F2C230", "#1B1B1B"),
    ("#1E7F4F", "#FFFFFF"),
    ("#6A2C91", "#F5D547"),
    ("#E8682A", "#0E1C36"),
    ("#2BB3D6", "#0B2239"),
    ("#E6E6E6", "#C8102E"),
    ("#111111", "#E3B505"),
    ("#8B1E3F", "#7FB7E5"),
    ("#2F4858", "#F6AE2D"),
    ("#D7263D", "#1B998B"),
)

# Anchors in the attacking frame, normalised: ax from own goal (0) to opponent goal (1).
FORMATIONS: dict[str, list[tuple[str, float, float]]] = {
    "4-3-3": [
        ("GK", 0.04, 0.50),
        ("LB", 0.24, 0.86),
        ("CB", 0.18, 0.62),
        ("CB", 0.18, 0.38),
        ("RB", 0.24, 0.14),
        ("CM", 0.42, 0.68),
        ("DM", 0.34, 0.50),
        ("CM", 0.42, 0.32),
        ("LW", 0.63, 0.85),
        ("ST", 0.67, 0.50),
        ("RW", 0.63, 0.15),
    ],
    "4-4-2": [
        ("GK", 0.04, 0.50),
        ("LB", 0.24, 0.86),
        ("CB", 0.18, 0.62),
        ("CB", 0.18, 0.38),
        ("RB", 0.24, 0.14),
        ("LM", 0.46, 0.85),
        ("CM", 0.40, 0.60),
        ("CM", 0.40, 0.40),
        ("RM", 0.46, 0.15),
        ("ST", 0.65, 0.60),
        ("ST", 0.65, 0.40),
    ],
    "4-2-3-1": [
        ("GK", 0.04, 0.50),
        ("LB", 0.24, 0.86),
        ("CB", 0.18, 0.62),
        ("CB", 0.18, 0.38),
        ("RB", 0.24, 0.14),
        ("DM", 0.34, 0.60),
        ("DM", 0.34, 0.40),
        ("LW", 0.56, 0.83),
        ("AM", 0.54, 0.50),
        ("RW", 0.56, 0.17),
        ("ST", 0.68, 0.50),
    ],
    "3-5-2": [
        ("GK", 0.04, 0.50),
        ("CB", 0.18, 0.72),
        ("CB", 0.17, 0.50),
        ("CB", 0.18, 0.28),
        ("LWB", 0.52, 0.90),
        ("CM", 0.46, 0.66),
        ("DM", 0.34, 0.50),
        ("CM", 0.46, 0.34),
        ("RWB", 0.52, 0.10),
        ("ST", 0.65, 0.60),
        ("ST", 0.65, 0.40),
    ],
}
BENCH = ("GK", "CB", "CM", "LW", "ST")

LINE = {
    "GK": "GK",
    "LB": "DEF",
    "RB": "DEF",
    "CB": "DEF",
    "LWB": "DEF",
    "RWB": "DEF",
    "DM": "MID",
    "CM": "MID",
    "AM": "MID",
    "LM": "MID",
    "RM": "MID",
    "LW": "FWD",
    "RW": "FWD",
    "ST": "FWD",
}
WIDE = {"LB", "RB", "LWB", "RWB", "LM", "RM", "LW", "RW"}


@cache
def blocklist() -> dict[str, frozenset[str]]:
    """Sections of the blocklist: surnames, clubs, towns (lower-case entries)."""
    sections: dict[str, set[str]] = {"surnames": set(), "clubs": set(), "towns": set()}
    current = ""
    for raw in BLOCKLIST_PATH.read_text().splitlines():
        line = raw.strip().lower()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            current = line.strip("[]")
            continue
        sections[current].update(e.strip() for e in line.split(",") if e.strip())
    return {k: frozenset(v) for k, v in sections.items()}


def is_real_surname(name: str) -> bool:
    bl = blocklist()
    return name.lower() in bl["surnames"] or name.lower() in bl["towns"]


def is_real_town(town: str) -> bool:
    """A town is blocked if it is a listed town or the first word(s) of a real club."""
    bl = blocklist()
    t = town.lower()
    return t in bl["towns"] or any(c == t or c.startswith(t + " ") for c in bl["clubs"])


def is_real_club(full: str) -> bool:
    return full.lower() in blocklist()["clubs"] or is_real_town(full.split()[0])


@dataclass(frozen=True)
class TeamSheet:
    team: Team
    players: list[Player]  # 11 starters in formation order, then bench
    anchors: list[tuple[float, float]]  # starters only, attacking frame, normalised


def _pick(rng: np.random.Generator, items: tuple[str, ...]) -> str:
    return items[int(rng.integers(len(items)))]


def _town(rng: np.random.Generator, taken: set[str]) -> str:
    while True:
        name = _pick(rng, TOWN_START) + _pick(rng, TOWN_END)
        if name not in taken and not is_real_town(name):
            return name


def _surname(rng: np.random.Generator) -> str:
    while True:
        name = _pick(rng, SURNAME_START) + _pick(rng, SURNAME_END)
        if not is_real_surname(name):
            return name


def _attrs(rng: np.random.Generator, pos: str) -> PlayerAttrs:
    line = LINE[pos]

    def u(lo: float, hi: float) -> float:
        return round(float(rng.uniform(lo, hi)), 2)

    top = u(8.0, 8.6) if line == "GK" else u(8.7, 9.9)
    if pos in WIDE or line == "FWD":
        top = min(9.95, round(top + 0.15, 2))
    return PlayerAttrs(
        top_speed_ms=top,
        accel=u(0.45, 0.95),
        passing=u(0.55, 0.9) if line in ("MID", "DEF") else u(0.45, 0.8),
        finishing=u(0.6, 0.92) if line == "FWD" else u(0.25, 0.6),
        defending=u(0.6, 0.92) if line in ("DEF", "GK") else u(0.3, 0.7),
        stamina=u(0.4, 0.95),
    )


def _team(rng: np.random.Generator, taken_towns: set[str], color_idx: int) -> TeamSheet:
    town = _town(rng, taken_towns)
    taken_towns.add(town)
    name = f"{town} {_pick(rng, CLUB_SUFFIX)}"
    short = town[:3].upper()
    team_id = f"t_{short.lower()}"
    formation = list(FORMATIONS)[int(rng.integers(len(FORMATIONS)))]
    style = TeamStyle(
        press_intensity=round(float(rng.uniform(0.35, 0.7)), 2),
        directness=round(float(rng.uniform(0.25, 0.6)), 2),
        width=round(float(rng.uniform(0.35, 0.7)), 2),
    )
    team = Team(
        team_id=team_id,
        name=name,
        short=short,
        colors=list(COLOR_PAIRS[color_idx]),
        formation=formation,
        style=style,
    )
    shape = FORMATIONS[formation]
    positions = [p for p, _, _ in shape] + list(BENCH)
    outfield = [n for n in range(2, 30) if n != 13]
    picks = rng.choice(np.array(outfield), size=len(positions) - 2, replace=False)
    shirts = [1, *(int(n) for n in picks[:10]), 13, *(int(n) for n in picks[10:])]
    players = []
    used_names: set[str] = set()
    for i, (pos, shirt) in enumerate(zip(positions, shirts, strict=True)):
        while True:
            full = f"{_pick(rng, FIRST_NAMES)} {_surname(rng)}"
            if full not in used_names:
                used_names.add(full)
                break
        players.append(
            Player(
                player_id=f"p_{short.lower()}_{shirt:02d}",
                team_id=team_id,
                name=full,
                shirt=shirt,
                position=pos,
                starter=i < 11,
                attrs=_attrs(rng, pos),
            )
        )
    anchors = [(ax, ay) for _, ax, ay in shape]
    return TeamSheet(team=team, players=players, anchors=anchors)


def build(rng: np.random.Generator) -> tuple[TeamSheet, TeamSheet, str]:
    """Home sheet, away sheet, venue name."""
    taken: set[str] = set()
    c1, c2 = (int(c) for c in rng.choice(len(COLOR_PAIRS), size=2, replace=False))
    home = _team(rng, taken, c1)
    while True:
        away = _team(rng, taken, c2)
        if away.team.short != home.team.short:
            break
        taken.add(away.team.name.split()[0])
    venue = f"{home.team.name.split()[0]} {_pick(rng, VENUE_SUFFIX)}"
    return home, away, venue
