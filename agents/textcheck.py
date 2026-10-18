"""Code checks on derived text (captions, persona lines): they may only restate the verified
claim. Every number must appear in the claim (same rounding or the percent form), and every
player named must be one the claim or the moment names. Lines that fail fall back to a
template built from the verified claim.
"""

import re

NUMBER = re.compile(r"\d+(?:[.,]\d+)?")


def numbers(text: str) -> set[str]:
    return {n.replace(",", ".") for n in NUMBER.findall(text)}


def allowed_numbers(claim: str, extra: set[str]) -> set[str]:
    out = set(extra)
    for n in numbers(claim):
        out.add(n)
        v = float(n)
        out |= {f"{v:g}", str(round(v)), f"{v:.1f}"}
    return out


def problems(
    text: str, claim: str, players: dict[str, str], allowed_names: set[str], extra_numbers: set[str]
) -> list[str]:
    """Reasons `text` says more than the claim; empty if it only restates it."""
    out = [
        f"number {n} not in the verified claim"
        for n in sorted(numbers(text) - allowed_numbers(claim, extra_numbers))
    ]
    for name in players.values():
        surname = name.split()[-1]
        if surname in text and name not in allowed_names:
            out.append(f"names {name}, who is not part of the verified claim")
    return out
