"""Canonical bytes, content identity, and dataset manifests for S01 artifacts.

Canonical JSON: sort_keys, separators (',', ':'), UTF-8, no NaN. Content id = SHA-256 of
canonical bytes. A content id is an identity, never an address and never reversible.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from src.fmo import fmo_root, leaf, sha256_file

ROOT = Path(__file__).resolve().parents[2]


def cbytes(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode()


def content_id(obj) -> str:
    return "sha256:" + hashlib.sha256(cbytes(obj)).hexdigest()


def git_head() -> str:
    p = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    return p.stdout.strip() or "UNKNOWN"


def write_jsonl(path: Path, rows) -> tuple[str, int, int]:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(path, "wb") as f:
        for r in rows:
            f.write(cbytes(r) + b"\n")
            n += 1
    sha, nb = sha256_file(path)
    return sha, nb, n


def write_manifest(ds_dir: Path, *, dataset_id: str, schema: str, kind: str, source: str,
                   generation_code: list[str], config: dict, seeds, license: str = "CC-BY-4.0",
                   parent_evidence: list[str] | None = None, claim_ceiling: str,
                   visibility: str = "public") -> dict:
    files = sorted(p for p in ds_dir.iterdir() if p.is_file() and p.name != "MANIFEST.json")
    recs, groups = [], {"data": []}
    for p in files:
        rel = str(p.relative_to(ROOT))
        sha, nb = sha256_file(p)
        recs.append({"path": rel, "bytes": nb, "sha256": sha})
        groups["data"].append((rel, leaf(rel, nb, sha)))
    code = []
    for c in generation_code:
        sha, nb = sha256_file(ROOT / c)
        code.append({"path": c, "sha256": sha})
    root, _ = fmo_root(groups)
    m = {"dataset_id": dataset_id, "kind": kind, "schema": schema, "source": source,
         "license": license, "generation_code": code, "code_commit_at_generation": git_head(),
         "config": config, "seeds": seeds, "files": recs, "fmo_root": root,
         "visibility": visibility, "parent_evidence": parent_evidence or [],
         "claim_ceiling": claim_ceiling}
    (ds_dir / "MANIFEST.json").write_text(json.dumps(m, indent=2) + "\n")
    return m
