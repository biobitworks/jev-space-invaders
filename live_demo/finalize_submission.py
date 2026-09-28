#!/usr/bin/env python3
"""Fail-closed final competition submission after live-demo acceptance.

Private contact fields are loaded only from entry.local.json (or --source).
Nothing private is written to Git. Sponsor booleans default to conservative
false/false unless the operator explicitly selects receipt-backed mode.
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
ENTRY_API = "https://mitosislabs.ai/api/ufa/jev/entries"
REPO_URL = "https://github.com/biobitworks/jev-space-invaders"


def public_url(u: str) -> bool:
    p = urlparse(u)
    return p.scheme == "https" and bool(p.netloc)


def get_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=str(ROOT / "entry.local.json"))
    ap.add_argument("--acceptance", default="/tmp/vithia-space-live-demo/ACCEPTANCE_RECEIPT.json")
    ap.add_argument("--demo-video-url", required=True)
    ap.add_argument("--sponsor-mode", choices=["conservative", "receipt-backed"], default="conservative")
    ap.add_argument("--allow-2p-blocked", action="store_true")
    ap.add_argument("--payload-out", default="/tmp/vithia-space-live-demo/entry.resubmit.local.json")
    ap.add_argument("--response-out", default="/tmp/vithia-space-live-demo/FINAL_SUBMISSION_RESPONSE.json")
    a = ap.parse_args()

    if not public_url(a.demo_video_url):
        raise SystemExit("DEMO_URL_INVALID")
    try:
        with urllib.request.urlopen(a.demo_video_url, timeout=20) as r:
            if r.status >= 400:
                raise SystemExit(f"DEMO_URL_HTTP_{r.status}")
    except Exception as e:
        raise SystemExit(f"DEMO_URL_NOT_PUBLIC:{e}")

    acc = get_json(Path(a.acceptance))
    allowed = {"PASS"}
    if a.allow_2p_blocked:
        allowed.add("PASS_WITH_EXPLICIT_2P_BLOCK")
    if acc.get("overall") not in allowed:
        raise SystemExit(f"ACCEPTANCE_GATE_FAIL:{acc.get('overall')}")
    if acc.get("one_player", {}).get("state") != "PASS":
        raise SystemExit("1P_ACCEPTANCE_REQUIRED")
    if not a.allow_2p_blocked and acc.get("two_player", {}).get("state") != "PASS":
        raise SystemExit("2P_ACCEPTANCE_REQUIRED")

    src = Path(a.source)
    if not src.exists():
        raise SystemExit("PRIVATE_ENTRY_SOURCE_MISSING")
    payload = json.loads(src.read_text())
    payload.setdefault("build", {})["repo_url"] = REPO_URL
    payload["build"]["demo_video_url"] = a.demo_video_url
    payload["needs_jev_access"] = True
    payload.setdefault("sponsors", {})

    if a.sponsor_mode == "conservative":
        payload["sponsors"]["mitosis"] = False
        payload["sponsors"]["tenki"] = False
        payload["sponsors"]["how"] = (
            "Mitosis and Tenki have governed project evidence, but final competition "
            "sponsor booleans remain false unless the stricter load-bearing/current-access gate passes."
        )
    else:
        m = get_json(ROOT / "evidence/competition/final_execution/MITOSIS_FINAL_EXECUTION_RECEIPT.json")
        t = get_json(ROOT / "evidence/competition/final_execution/TENKI_FINAL_EXECUTION_RECEIPT.json")
        payload["sponsors"]["mitosis"] = m.get("MITOSIS_USED") is True
        payload["sponsors"]["tenki"] = t.get("TENKI_USED") is True
        payload["sponsors"]["how"] = (
            f"Mitosis final state={m.get('state','UNKNOWN')}; "
            f"Tenki final state={t.get('state','UNKNOWN')}."
        )

    out = Path(a.payload_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n")
    os.chmod(out, 0o600)

    send = json.loads(json.dumps(payload))
    send["submitted_via"] = "api"
    req = urllib.request.Request(
        ENTRY_API, data=json.dumps(send).encode(),
        headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = json.loads(r.read())
    except Exception as e:
        raise SystemExit(f"SUBMISSION_HTTP_ERROR:{e}")

    Path(a.response_out).write_text(json.dumps(body, indent=2) + "\n")
    print(json.dumps(body, indent=2))
    if body.get("ok") is not True:
        raise SystemExit("SUBMISSION_OK_FALSE")
    if body.get("missing_for_judging") not in ([], None):
        raise SystemExit(f"MISSING_FOR_JUDGING:{body.get('missing_for_judging')}")
    print("FINAL_SUBMISSION_GATE=PASS")


if __name__ == "__main__":
    main()
