#!/usr/bin/env python3
"""Prepare a local UFA JEV entry resubmission payload. Never sends a network request."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from urllib.parse import urlparse

REPO_URL = "https://github.com/biobitworks/jev-space-invaders"
SPONSOR_HOW = (
    "Mitosis Cortex and Tenki were proposed but not executed; "
    "no load-bearing sponsor execution receipt exists."
)


def fail(message: str):
    raise SystemExit(f"PREPARE_STATE=FAIL\n{message}")


def valid_public_url(value: str) -> bool:
    p = urlparse(value)
    return p.scheme == "https" and bool(p.netloc)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="entry.local.json")
    ap.add_argument("--output", default="entry.resubmit.local.json")
    ap.add_argument("--demo-video-url", required=True)
    args = ap.parse_args()

    if not valid_public_url(args.demo_video_url):
        fail("DEMO_VIDEO_URL must be an https URL with a host")

    src = Path(args.source)
    if not src.exists():
        fail(f"SOURCE_MISSING:{src}")

    payload = json.loads(src.read_text())
    for key in ("team", "track", "pitch", "sponsors", "needs_jev_access", "in_person", "build"):
        if key not in payload:
            fail(f"SCHEMA_MISSING:{key}")
    if not isinstance(payload["sponsors"], dict):
        fail("SCHEMA_TYPE:sponsors")
    if not isinstance(payload["build"], dict):
        fail("SCHEMA_TYPE:build")

    out = json.loads(json.dumps(payload))
    out["build"]["repo_url"] = REPO_URL
    out["build"]["demo_video_url"] = args.demo_video_url
    out["sponsors"]["mitosis"] = False
    out["sponsors"]["tenki"] = False
    out["sponsors"]["how"] = SPONSOR_HOW
    out["needs_jev_access"] = True

    dst = Path(args.output)
    dst.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")
    os.chmod(dst, 0o600)

    raw = dst.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    public_summary = {
        "team": out["team"],
        "track": out["track"],
        "sponsors": {
            "mitosis": out["sponsors"]["mitosis"],
            "tenki": out["sponsors"]["tenki"],
            "how": out["sponsors"]["how"],
        },
        "needs_jev_access": out["needs_jev_access"],
        "in_person": out["in_person"],
        "build": {
            "repo_url": out["build"]["repo_url"],
            "demo_video_url": out["build"]["demo_video_url"],
        },
    }
    print("PREPARE_STATE=PASS")
    print(f"OUTPUT={dst}")
    print(f"OUTPUT_SHA256={sha}")
    print("NETWORK_REQUEST_PERFORMED=NO")
    print("PUBLIC_SUMMARY=" + json.dumps(public_summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
