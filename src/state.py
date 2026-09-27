from __future__ import annotations
from typing import Sequence

def encode_state(step: int, score: float, ram: Sequence[int], previous_ram: Sequence[int] | None, lives: int | None = None) -> dict:
    current = tuple(int(x) for x in ram)
    changed = () if previous_ram is None else tuple(i for i, (a, b) in enumerate(zip(previous_ram, current)) if int(a) != b)
    return {
        "step": int(step),
        "score": float(score),
        "lives": None if lives is None else int(lives),
        "ram": list(current),
        "delta_indices": list(changed),
    }
