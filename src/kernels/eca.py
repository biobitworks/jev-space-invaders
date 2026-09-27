"""Elementary cellular automata, rules 0-255 (Wolfram numbering), clean-room kernel.

Neighbourhood (l, c, r) -> index 4l+2c+r; next bit = (rule >> index) & 1.
Boundary: 'periodic' (ring) or 'zero' (cells outside are 0).
"""
from __future__ import annotations


def eca_step(row: list[int], rule: int, boundary: str = "periodic") -> list[int]:
    if not 0 <= rule <= 255:
        raise ValueError("rule must be in [0, 255]")
    n = len(row)
    out = [0] * n
    for i in range(n):
        if boundary == "periodic":
            l, r = row[i - 1], row[(i + 1) % n]
        else:
            l = row[i - 1] if i > 0 else 0
            r = row[i + 1] if i < n - 1 else 0
        out[i] = (rule >> (4 * l + 2 * row[i] + r)) & 1
    return out


def evolve(row: list[int], rule: int, steps: int, boundary: str = "periodic") -> list[list[int]]:
    rows = [list(row)]
    for _ in range(steps):
        rows.append(eca_step(rows[-1], rule, boundary))
    return rows


def neighbourhood_index(prev: list[int], i: int, boundary: str = "periodic") -> int | None:
    n = len(prev)
    if boundary == "periodic":
        l, c, r = prev[i - 1], prev[i], prev[(i + 1) % n]
    else:
        l = prev[i - 1] if i > 0 else 0
        c = prev[i]
        r = prev[i + 1] if i < n - 1 else 0
    if None in (l, c, r):
        return None
    return 4 * l + 2 * c + r
