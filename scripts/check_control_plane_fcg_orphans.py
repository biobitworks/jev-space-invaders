#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FCOS = ROOT / "evidence/competition/control_plane/BP0014_ACTOR_CONTROL_PLANE_FCOS.json"
EDGES = ROOT / "evidence/competition/control_plane/BP0014_CONTROL_PLANE_FCG_EDGES.jsonl"
ALLOWED_PREDICATES = {
    "PRODUCED_BY",
    "EXECUTED_ON",
    "USED_SOFTWARE",
    "USED_MODEL",
    "USED_SERVICE",
    "VERIFIED_BY",
    "COMMITTED_BY",
    "SUPERSEDES",
}
ALLOWED_EXTERNAL = {"UFA-JEV-COMP-BP-0013"}


def main() -> int:
    bundle = json.loads(FCOS.read_text())
    known = {fco["id"] for fco in bundle["fcos"]}
    errors: list[str] = []
    edge_count = 0
    for line_number, line in enumerate(EDGES.read_text().splitlines(), 1):
        if not line.strip():
            continue
        edge_count += 1
        edge = json.loads(line)
        pred = edge.get("predicate")
        if pred not in ALLOWED_PREDICATES:
            errors.append(f"line {line_number}: predicate {pred!r} not allowed")
        for side in ("subject", "object"):
            value = edge.get(side)
            if value not in known and value not in ALLOWED_EXTERNAL:
                errors.append(f"line {line_number}: {side} {value!r} is orphaned")
    print("FCG_ORPHAN_CHECK=" + ("PASS" if not errors else "FAIL"))
    print("FCG_EDGE_COUNT=" + str(edge_count))
    if errors:
        for error in errors:
            print("ERROR=" + error)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
