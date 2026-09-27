"""J0 perception: deterministic RGB-frame -> compact JSON state (no raw RAM to the decider).

Colours are the ALE SpaceInvaders-v5 palette observed with ale-py 0.12.1. Objects the
parser cannot settle are reported as unknown rather than guessed (e.g. a shot seen
for the first time has direction "unknown" until it moves).
"""
from __future__ import annotations

import numpy as np

VERSION = "perception_v1"
SHIP_RGB = (50, 132, 50)
ALIEN_RGB = (134, 134, 29)
SHOT_RGB = (142, 142, 142)
SHIELD_RGB = (181, 83, 40)
SHIP_ROWS = (185, 195)       # [start, stop)
SHIELD_ROWS = (150, 185)
PLAYFIELD_ROWS = (20, 195)


def _mask(frame: np.ndarray, rgb, rows) -> np.ndarray:
    sub = frame[rows[0]:rows[1]]
    return (sub[..., 0] == rgb[0]) & (sub[..., 1] == rgb[1]) & (sub[..., 2] == rgb[2])


def _runs(idx: np.ndarray, gap: int = 1) -> list[tuple[int, int]]:
    """Consecutive-integer runs in a sorted index array -> [(start, end_inclusive)]."""
    if idx.size == 0:
        return []
    splits = np.where(np.diff(idx) > gap)[0]
    starts = np.concatenate(([idx[0]], idx[splits + 1]))
    ends = np.concatenate((idx[splits], [idx[-1]]))
    return [(int(a), int(b)) for a, b in zip(starts, ends)]


class Perception:
    def __init__(self) -> None:
        self.prev_shots: list[dict] = []
        self.prev_ship_x: float | None = None

    def reset(self) -> None:
        self.prev_shots, self.prev_ship_x = [], None

    def observe(self, frame: np.ndarray, *, lives: int, score: float, step: int,
                prev_action: str) -> dict:
        # ship
        m = _mask(frame, SHIP_RGB, SHIP_ROWS)
        xs = np.where(m.any(axis=0))[0]
        ship = None
        if xs.size:
            cx = float((xs.min() + xs.max()) / 2)
            ship = {"x": round(cx, 1), "x_min": int(xs.min()), "x_max": int(xs.max()),
                    "dx": None if self.prev_ship_x is None else round(cx - self.prev_ship_x, 1)}
            self.prev_ship_x = cx

        # shots: 1-px-wide vertical segments
        m = _mask(frame, SHOT_RGB, PLAYFIELD_ROWS)
        shots = []
        for x in np.where(m.any(axis=0))[0]:
            for y0, y1 in _runs(np.where(m[:, x])[0]):
                shots.append({"x": int(x), "y_top": y0 + PLAYFIELD_ROWS[0], "y_bottom": y1 + PLAYFIELD_ROWS[0]})
        for s in shots:
            best = None
            for p in self.prev_shots:
                if abs(p["x"] - s["x"]) <= 2 and abs(p["y_top"] - s["y_top"]) <= 20:
                    d = abs(p["y_top"] - s["y_top"])
                    if best is None or d < best[0]:
                        best = (d, s["y_top"] - p["y_top"])
            s["dy"] = None if best is None else best[1]
            if best is not None and best[1] > 0:
                s["kind"] = "bomb"
            elif best is not None and best[1] < 0:
                s["kind"] = "own_shot"
            else:
                s["kind"] = "unknown"
        self.prev_shots = shots

        # aliens
        m = _mask(frame, ALIEN_RGB, PLAYFIELD_ROWS)
        aliens = {"present": bool(m.any())}
        if m.any():
            ys = np.where(m.any(axis=1))[0]
            rows = _runs(ys, gap=2)
            count, lowest_by_col = 0, {}
            for y0, y1 in rows:
                cols = _runs(np.where(m[y0:y1 + 1].any(axis=0))[0], gap=2)
                count += len(cols)
                for c0, c1 in cols:
                    key = int((c0 + c1) // 2)
                    lowest_by_col[key] = max(lowest_by_col.get(key, 0), y1 + PLAYFIELD_ROWS[0])
            axs = np.where(m.any(axis=0))[0]
            aliens.update({"count_est": count, "rows": len(rows),
                           "x_min": int(axs.min()), "x_max": int(axs.max()),
                           "y_min": int(ys.min()) + PLAYFIELD_ROWS[0], "y_max": int(ys.max()) + PLAYFIELD_ROWS[0],
                           "column_centres_x": sorted(lowest_by_col)[:12]})

        # shields
        m = _mask(frame, SHIELD_RGB, SHIELD_ROWS)
        shields = []
        for c0, c1 in _runs(np.where(m.any(axis=0))[0], gap=3):
            shields.append({"x_min": c0, "x_max": c1, "pixels": int(m[:, c0:c1 + 1].sum())})

        bombs = [s for s in shots if s["kind"] == "bomb"]
        return {
            "encoding": VERSION,
            "coords": "x 0-159 left->right (RIGHT increases x); y 0-209 top->bottom; ship row y 185-194",
            "step": step, "score": float(score), "lives": int(lives), "previous_action": prev_action,
            "ship": ship,
            "bombs": [{k: s[k] for k in ("x", "y_bottom", "dy")} for s in bombs],
            "own_shots": [{k: s[k] for k in ("x", "y_top")} for s in shots if s["kind"] == "own_shot"],
            "unknown_shots": [{k: s[k] for k in ("x", "y_top", "y_bottom")} for s in shots if s["kind"] == "unknown"],
            "aliens": aliens,
            "shields": shields,
        }
