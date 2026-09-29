#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
REPLAY = ROOT / "publication" / "replay" / "v0.1.0"


def write_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--output", default=str(ROOT / "publication" / "replay" / "gumdoctor3" / "GUMDOCTOR3_PUBLICATION_REPLAY_RECEIPT.json"))
    args = parser.parse_args()
    output = Path(args.output)
    deterministic_out = output.parent / "deterministic"
    cmd = [
        sys.executable,
        str(REPLAY / "scripts" / "rebuild_publication_from_root.py"),
        "--root",
        args.root,
        "--store",
        str(REPLAY),
        "--output",
        str(deterministic_out),
        "--offline-strict",
    ]
    proc = subprocess.run(cmd, text=True, capture_output=True)
    receipt_path = deterministic_out / "PUBLICATION_REPLAY_RECEIPT.json"
    deterministic_receipt = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.exists() else {}
    receipt = {
        "schema": "GUMDOCTOR3_PUBLICATION_REPLAY_RECEIPT_V1",
        "created_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "gumdoctor3_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "adapter_config_state": "NON_LOAD_BEARING_DETERMINISTIC_REPLAY_ONLY",
        "model_census_state": "RECORDED",
        "publication_replay_tool_bound": True,
        "root_used": args.root,
        "deterministic_receipt_ref": str(receipt_path.relative_to(ROOT)),
        "deterministic_result": deterministic_receipt.get("rebuild_from_root", "MISSING_RECEIPT"),
        "optional_review_lanes": [],
        "review_failures": [],
        "secret_scan": deterministic_receipt.get("secret_scan", "NOT_RUN"),
        "overall": "PASS" if proc.returncode == 0 and deterministic_receipt.get("rebuild_from_root") == "PASS" else "FAIL",
        "stdout_tail": proc.stdout[-1000:],
        "stderr_tail": proc.stderr[-1000:],
    }
    write_json(output, receipt)
    print(f"GUMDOCTOR3_PUBLICATION_REPLAY={receipt['overall']}")
    return 0 if receipt["overall"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
