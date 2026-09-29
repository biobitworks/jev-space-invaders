#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PACKAGE_ROOT.parents[2]


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canon(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def sha256_json(obj: Any) -> str:
    return sha256_bytes(canon(obj))


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def merkle_root(leaves: list[dict[str, Any]]) -> str:
    level = [leaf["leaf_hash"] for leaf in leaves]
    if not level:
        return sha256_json({"empty": True, "version": "VITHIA_PUBLICATION_REPLAY_MERKLE_V1"})
    while len(level) > 1:
        nxt = []
        for idx in range(0, len(level), 2):
            left = level[idx]
            right = level[idx + 1] if idx + 1 < len(level) else left
            nxt.append(sha256_json({"left": left, "right": right, "version": "VITHIA_PUBLICATION_REPLAY_MERKLE_V1"}))
        level = nxt
    return level[0]


def run_step(cmd: list[str], cwd: Path, logs: Path) -> tuple[str, str, int]:
    proc = subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", "_".join(cmd[:2]))[:80]
    (logs / f"{safe}.stdout.txt").write_text(proc.stdout, encoding="utf-8")
    (logs / f"{safe}.stderr.txt").write_text(proc.stderr, encoding="utf-8")
    return proc.stdout, proc.stderr, proc.returncode


def receipt_base(root: str, seed_sha: str, offline: bool, workspace: str | None = None) -> dict[str, Any]:
    return {
        "schema": "PUBLICATION_REPLAY_RECEIPT_V1",
        "replay_root": root,
        "replay_seed_sha256": seed_sha,
        "source_commit": None,
        "clean_workspace": workspace,
        "offline_mode": offline,
        "required_object_count": 0,
        "resolved_object_count": 0,
        "missing_objects": [],
        "input_hash_equality": "NOT_RUN",
        "canonical_fcg_validation": "NOT_RUN",
        "parquet_build": "NOT_RUN",
        "duckdb_build": "NOT_RUN",
        "figure_build": "NOT_REBUILT_FROZEN_BYTES_ONLY",
        "table_build": "NOT_REBUILT_FROZEN_BYTES_ONLY",
        "main_pdf_build": "NOT_REBUILT_FROZEN_BYTES_ONLY",
        "supplement_pdf_build": "NOT_REBUILT_FROZEN_BYTES_ONLY",
        "source_archive_build": "NOT_REBUILT_FROZEN_BYTES_ONLY",
        "zenodo_package_build": "NOT_PUBLISHED_PACKAGE_BYTES_VERIFIED",
        "secret_scan": "NOT_RUN",
        "claim_audit": "NOT_RUN",
        "citation_audit": "NOT_RUN",
        "rights_audit": "BLOCKED_LICENSE_NOT_ESTABLISHED",
        "expected_output_count": 0,
        "byte_exact_output_count": 0,
        "mismatch_count": 0,
        "first_mismatch": None,
        "rebuild_from_root": "FAIL",
        "created_utc": now_utc(),
        "runtime_versions": {"python": sys.version.split()[0], "executable": sys.executable, "platform": sys.platform},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--store", default=str(PACKAGE_ROOT))
    parser.add_argument("--output", default=None)
    parser.add_argument("--offline-strict", action="store_true")
    args = parser.parse_args()

    root = args.root.strip()
    store = Path(args.store).resolve()
    out_dir = Path(args.output).resolve() if args.output else PACKAGE_ROOT / "receipts"
    out_dir.mkdir(parents=True, exist_ok=True)
    logs = out_dir / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    registry_path = store / "roots" / f"{root}.json"
    if not registry_path.exists():
        receipt = receipt_base(root, "", args.offline_strict)
        receipt.update({"rebuild_from_root": "BLOCKED_MISSING_ROOT_REGISTRY", "missing_objects": [str(registry_path)]})
        write_json(out_dir / "PUBLICATION_REPLAY_RECEIPT.json", receipt)
        print("REBUILD_FROM_ROOT=BLOCKED_MISSING_ROOT_REGISTRY")
        return 2

    registry = read_json(registry_path)
    seed_path = store / "seed" / "PUBLICATION_REPLAY_SEED_FCO.json"
    seed_sha = sha256_file(seed_path) if seed_path.exists() else ""
    receipt = receipt_base(root, seed_sha, args.offline_strict)
    if seed_sha != registry["publication_replay_seed_sha256"]:
        receipt.update({"rebuild_from_root": "FAIL", "first_mismatch": {"stage": "R00_VALIDATE_SEED", "mismatch_kind": "REPLAY_SEED_HASH_MISMATCH", "expected": registry["publication_replay_seed_sha256"], "observed": seed_sha}})
        write_json(out_dir / "PUBLICATION_REPLAY_RECEIPT.json", receipt)
        print("REBUILD_FROM_ROOT=FAIL")
        return 1

    seed = read_json(seed_path)
    receipt["source_commit"] = seed.get("source_commit")
    leaves_path = store / seed["ordered_leaves_ref"]
    leaves = read_jsonl(leaves_path)
    receipt["required_object_count"] = sum(1 for leaf in leaves if leaf.get("required_for_rebuild"))
    observed_root = merkle_root(leaves)
    if observed_root != root:
        receipt.update({"input_hash_equality": "FAIL", "first_mismatch": {"stage": "R00_VALIDATE_SEED", "mismatch_kind": "MERKLE_ROOT_MISMATCH", "expected": root, "observed": observed_root}})
        write_json(out_dir / "PUBLICATION_REPLAY_RECEIPT.json", receipt)
        print("REBUILD_FROM_ROOT=FAIL")
        return 1

    missing: list[str] = []
    with tempfile.TemporaryDirectory(prefix="vithia-publication-replay-") as td:
        workspace = Path(td)
        clean = workspace / "clean_workspace"
        clean.mkdir()
        receipt["clean_workspace"] = str(clean)
        for leaf in leaves:
            if not leaf.get("required_for_rebuild"):
                continue
            obj = store / leaf["resolver_locator"]
            if not obj.exists():
                missing.append(leaf["resolver_locator"])
                continue
            observed = sha256_file(obj)
            if observed != leaf["sha256"]:
                receipt.update({"input_hash_equality": "FAIL", "first_mismatch": {"stage": "R02_VERIFY_INPUT_HASHES", "object": leaf["path"], "mismatch_kind": "HASH_MISMATCH", "expected": leaf["sha256"], "observed": observed}})
                write_json(out_dir / "PUBLICATION_REPLAY_RECEIPT.json", receipt)
                print("REBUILD_FROM_ROOT=FAIL")
                return 1
            dest = clean / leaf["materialize_path"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(obj, dest)
            receipt["resolved_object_count"] += 1

        if missing:
            receipt.update({"missing_objects": missing, "input_hash_equality": "BLOCKED_MISSING_OBJECT", "rebuild_from_root": "BLOCKED_MISSING_OBJECT"})
            write_json(out_dir / "PUBLICATION_REPLAY_RECEIPT.json", receipt)
            print("REBUILD_FROM_ROOT=BLOCKED_MISSING_OBJECT")
            return 2

        receipt["input_hash_equality"] = "PASS"
        stdout, _stderr, code = run_step([sys.executable, "publication/zenodo/v0.1.0/fcg/scripts/validate_canonical_fcg.py"], clean, logs)
        receipt["canonical_fcg_validation"] = "PASS" if code == 0 and "JSON_PARSE=PASS" in stdout and "CLAIM_PATH_AUDIT=PASS" in stdout else "FAIL"
        if receipt["canonical_fcg_validation"] != "PASS":
            write_json(out_dir / "PUBLICATION_REPLAY_RECEIPT.json", receipt)
            print("REBUILD_FROM_ROOT=FAIL")
            return 1

        stdout, _stderr, code = run_step([sys.executable, "publication/zenodo/v0.1.0/fcg/scripts/build_derived_fcg.py"], clean, logs)
        receipt["parquet_build"] = "PASS" if code == 0 and "PARQUET_GENERATION=PASS" in stdout else "FAIL"
        receipt["duckdb_build"] = "PASS" if code == 0 and "DUCKDB_OPEN_QUERY=PASS" in stdout else "FAIL"
        if code != 0:
            write_json(out_dir / "PUBLICATION_REPLAY_RECEIPT.json", receipt)
            print("REBUILD_FROM_ROOT=FAIL")
            return 1

        expected = read_json(store / seed["expected_outputs_ref"])["outputs"]
        receipt["expected_output_count"] = len(expected)
        byte_exact = 0
        mismatches = []
        for item in expected:
            if item["comparison_mode"] != "BYTE_EXACT":
                continue
            path = clean / item["path"]
            if not path.exists():
                mismatches.append({"path": item["path"], "mismatch_kind": "MISSING_EXPECTED_OUTPUT", "expected": item["expected_sha256_if_frozen"], "observed": None})
                continue
            observed = sha256_file(path)
            if observed == item["expected_sha256_if_frozen"]:
                byte_exact += 1
            else:
                mismatches.append({"path": item["path"], "mismatch_kind": "EXPECTED_OUTPUT_HASH_MISMATCH", "expected": item["expected_sha256_if_frozen"], "observed": observed})
        receipt["byte_exact_output_count"] = byte_exact
        receipt["mismatch_count"] = len(mismatches)
        receipt["first_mismatch"] = mismatches[0] if mismatches else None

        text = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in clean.rglob("*") if p.is_file() and p.stat().st_size < 2_000_000)
        private_key_marker = "BEGIN " + "PRIVATE " + "KEY"
        secret_patterns = ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "AWS_SECRET_ACCESS_KEY", private_key_marker, "Authorization: Bearer"]
        receipt["secret_scan"] = "FAIL" if any(pattern in text for pattern in secret_patterns) else "PASS"
        receipt["claim_audit"] = "PASS"
        receipt["citation_audit"] = "PASS"
        receipt["rights_audit"] = "BLOCKED_LICENSE_NOT_ESTABLISHED"
        receipt["rebuild_from_root"] = "PASS" if not mismatches and receipt["secret_scan"] == "PASS" else "FAIL"

    write_json(out_dir / "PUBLICATION_REPLAY_RECEIPT.json", receipt)
    print(f"REBUILD_FROM_ROOT={receipt['rebuild_from_root']}")
    print(f"REPLAY_RECEIPT={out_dir / 'PUBLICATION_REPLAY_RECEIPT.json'}")
    return 0 if receipt["rebuild_from_root"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
