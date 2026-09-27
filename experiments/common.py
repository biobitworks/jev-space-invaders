from __future__ import annotations

import hashlib
import json
from pathlib import Path

from src.s01.canon import ROOT, write_jsonl, write_manifest  # noqa: F401

DATA = ROOT / "data" / "s01"
PREREG = ROOT / "docs" / "prereg"


def ds_dir(dataset_id: str) -> Path:
    d = DATA / dataset_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def read_jsonl(path: Path):
    with open(path, "rb") as f:
        for line in f:
            yield json.loads(line)


def rseed(*parts) -> int:
    return int.from_bytes(hashlib.sha256("|".join(map(str, parts)).encode()).digest()[:8], "big")


def prereg_ref(name: str) -> dict:
    p = PREREG / name
    return {"path": str(p.relative_to(ROOT)), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
