"""Conway's Game of Life (B3/S23) on a bounded torus, plus three explicit description scales.

CELL            the exact grid bits (source atoms; never mutated after observation)
LOCAL_PATTERN   the 3x3 neighbourhood bits around a site
PERSISTENT_OBJECT  8-connected components, identified by canonical shape (translation- and
                   rotation/reflection-normalised) against a small named catalogue
"""
from __future__ import annotations

import numpy as np

CATALOGUE_CELLS = {
    "block": ["11", "11"],
    "beehive": ["0110", "1001", "0110"],
    "loaf": ["0110", "1001", "0101", "0010"],
    "boat": ["110", "101", "010"],
    "tub": ["010", "101", "010"],
    "blinker": ["111"],
    "toad": ["0111", "1110"],
    "beacon": ["1100", "1100", "0011", "0011"],
    "glider": ["010", "001", "111"],
    "lwss": ["01001", "10000", "10001", "11110"],
}


def parse(rows: list[str]) -> np.ndarray:
    return np.array([[int(c) for c in r] for r in rows], dtype=np.uint8)


def step(g: np.ndarray) -> np.ndarray:
    n = sum(np.roll(np.roll(g, dy, 0), dx, 1) for dy in (-1, 0, 1) for dx in (-1, 0, 1)
            if (dy, dx) != (0, 0))
    return ((n == 3) | ((g == 1) & (n == 2))).astype(np.uint8)


def place(shape: np.ndarray, h: int, w: int, y: int, x: int, g: np.ndarray | None = None) -> np.ndarray:
    g = np.zeros((h, w), np.uint8) if g is None else g.copy()
    sh, sw = shape.shape
    g[y:y + sh, x:x + sw] |= shape
    return g


def _canon(cells: np.ndarray) -> bytes:
    """Minimal byte form over the 8 symmetries of the cropped shape."""
    ys, xs = np.nonzero(cells)
    c = cells[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    forms = []
    for k in range(4):
        r = np.rot90(c, k)
        for f in (r, np.fliplr(r)):
            forms.append(f"{f.shape[0]}x{f.shape[1]}:".encode() + np.packbits(f).tobytes())
    return min(forms)


def _phases(rows: list[str], n: int = 4) -> set[bytes]:
    """Canonical forms of every phase of a catalogue pattern (run on an isolated grid)."""
    s = parse(rows)
    g = place(s, 24, 24, 8, 8)
    out = set()
    for _ in range(n):
        if g.any():
            out.add(_canon(g))
        g = step(g)
    return out


CATALOGUE = {name: _phases(rows) for name, rows in CATALOGUE_CELLS.items()}


def components(g: np.ndarray) -> list[np.ndarray]:
    """8-connected components on the torus -> list of boolean masks."""
    h, w = g.shape
    seen = np.zeros_like(g, bool)
    comps = []
    for y, x in zip(*np.nonzero(g)):
        if seen[y, x]:
            continue
        mask = np.zeros_like(g, bool)
        stack = [(y, x)]
        seen[y, x] = True
        while stack:
            cy, cx = stack.pop()
            mask[cy, cx] = True
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = (cy + dy) % h, (cx + dx) % w
                    if g[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
        comps.append(mask)
    return comps


def classify(mask: np.ndarray, g: np.ndarray) -> str:
    cells = (g & mask).astype(np.uint8)
    # unwrap torus crossing by rolling to the component's first cell
    ys, xs = np.nonzero(cells)
    cells = np.roll(np.roll(cells, -int(ys.min()) + 2, 0), -int(xs.min()) + 2, 1)
    form = _canon(cells)
    for name, forms in CATALOGUE.items():
        if form in forms:
            return name
    return f"unknown:{int(cells.sum())}"


def objects(g: np.ndarray) -> list[str]:
    return sorted(classify(m, g) for m in components(g))


def local_pattern(g: np.ndarray, y: int, x: int) -> int:
    h, w = g.shape
    bits = 0
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            bits = (bits << 1) | int(g[(y + dy) % h, (x + dx) % w])
    return bits


def _centroids(g: np.ndarray) -> list[tuple[str, float, float]]:
    out = []
    for m in components(g):
        ys, xs = np.nonzero(m)
        out.append((classify(m, g), float(ys.mean()), float(xs.mean())))
    return out


def kinematics(history: list[np.ndarray], lag: int = 4) -> list[dict]:
    """Context projection that needs history: per object in the LAST frame, displacement
    against the frame `lag` positions earlier in the supplied history (period 4 covers the
    glider and LWSS). With fewer than lag+1 frames the motion label is UNKNOWN."""
    cur = history[-1]
    h, w = cur.shape
    now = _centroids(cur)
    if len(history) <= lag:
        return [{"object": c, "motion": "UNKNOWN", "d": None} for c, _, _ in now]
    before = _centroids(history[-1 - lag])
    out = []
    for c, y, x in now:
        cands = [(b, by, bx) for b, by, bx in before if b == c]
        if not cands:
            out.append({"object": c, "motion": "UNKNOWN", "d": None})
            continue

        def wrap(d, n):
            return (d + n / 2) % n - n / 2

        dy, dx = min(((wrap(y - by, h), wrap(x - bx, w)) for _, by, bx in cands), key=lambda d: abs(d[0]) + abs(d[1]))
        moving = abs(dy) > 0.5 or abs(dx) > 0.5
        out.append({"object": c, "motion": "MOVING" if moving else "STATIC", "d": [round(dy, 2), round(dx, 2)]})
    return sorted(out, key=lambda o: (o["object"], o["motion"]))


TRUE_MOTION = {"glider": "MOVING", "lwss": "MOVING", "block": "STATIC", "beehive": "STATIC", "loaf": "STATIC",
               "boat": "STATIC", "tub": "STATIC", "blinker": "STATIC", "toad": "STATIC", "beacon": "STATIC"}
