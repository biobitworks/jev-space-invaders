"""Strict elementary-cellular-automaton decomposition of 1P actions."""
from __future__ import annotations

from typing import Literal

Move = Literal["NONE", "LEFT", "RIGHT"]
Fire = Literal["NO", "YES"]

ECA_CLASSES: tuple[tuple[str, str, str], ...] = (
    ("NONE", "NO", "NOOP"),
    ("NONE", "YES", "FIRE"),
    ("LEFT", "NO", "LEFT"),
    ("LEFT", "YES", "LEFTFIRE"),
    ("RIGHT", "NO", "RIGHT"),
    ("RIGHT", "YES", "RIGHTFIRE"),
)
ECA_ACTIONS: tuple[str, ...] = tuple(action for _, _, action in ECA_CLASSES)
_COMPOSE = {(move, fire): action for move, fire, action in ECA_CLASSES}
_DECOMPOSE = {action: (move, fire) for move, fire, action in ECA_CLASSES}


def compose(move: Move, fire: Fire) -> str:
    """Return the unique counted action for one MOVE/FIRE pair."""
    try:
        return _COMPOSE[(move, fire)]
    except KeyError as exc:
        raise ValueError(f"invalid ECA class: MOVE={move!r} FIRE={fire!r}") from exc


def decompose(action: str) -> tuple[Move, Fire]:
    """Return the unique MOVE/FIRE pair for a counted action."""
    try:
        return _DECOMPOSE[action]
    except KeyError as exc:
        raise ValueError(f"invalid counted action: {action!r}") from exc


def round_trip(action: str) -> str:
    move, fire = decompose(action)
    return compose(move, fire)


if len(ECA_CLASSES) != 6 or len(_COMPOSE) != 6 or len(_DECOMPOSE) != 6:
    raise RuntimeError("ECA action decomposition is not a six-class bijection")
