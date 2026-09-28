#!/usr/bin/env python3
"""Low-noise terminal viewer: replays a recorded trace (.jsonl.gz from results.json
runs, or a frame-custody FRAME_BREAKPOINT_LEAVES.jsonl) as a compact status line
per decision. Operator monitoring only - never fed back into any model's input.
"""
from __future__ import annotations
import argparse, gzip, json, sys
from pathlib import Path


def replay_trace(path: Path, fps_nominal: float = 15.0) -> None:
    lines = gzip.open(path, "rt").readlines() if path.suffix == ".gz" else path.read_text().splitlines()
    for i, line in enumerate(lines):
        rec = json.loads(line)
        action = rec.get("action") or rec.get("vita_action", "?")
        score = rec.get("reward")
        print(f"FRAME={i:5d} DECISION={i:5d} ACTION={action:<10s} "
              f"LIVES={rec.get('lives', '?')!s:>2s} MS={rec.get('ms', 0):7.2f}")


def replay_leaves(path: Path) -> None:
    for line in path.read_text().splitlines():
        rec = json.loads(line)
        print(f"FRAME={rec['frame_index']:5d} ACTION={rec.get('action','?'):<10s} "
              f"SCORE={rec.get('score', '?')!s:>7s} LIVES={rec.get('lives', '?')!s:>2s} "
              f"FRAME_ROOT={rec['frame_root'][:12]}...")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", help="trace .jsonl.gz or FRAME_BREAKPOINT_LEAVES.jsonl")
    a = ap.parse_args()
    p = Path(a.path)
    if p.name == "FRAME_BREAKPOINT_LEAVES.jsonl":
        replay_leaves(p)
    else:
        replay_trace(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
