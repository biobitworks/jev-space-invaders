#!/usr/bin/env python3
"""Black-box acceptance for the local live gameplay browser.

Runs only against localhost. Writes a noncanonical receipt outside the repo by
default. 2P is required for overall PASS unless --allow-2p-blocked is explicit.
"""
from __future__ import annotations

import argparse
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def req(base: str, path: str, body=None):
    data = None if body is None else json.dumps(body).encode()
    r = urllib.request.Request(
        base.rstrip("/") + path, data=data,
        headers={"Content-Type": "application/json"},
        method="GET" if body is None else "POST",
    )
    with urllib.request.urlopen(r, timeout=40) as x:
        return json.loads(x.read())


def wait_step(base, old, timeout=45):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = req(base, "/api/state")
        if s.get("step", 0) > old:
            return s
        time.sleep(.2)
    raise TimeoutError("live step did not advance")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8788")
    ap.add_argument("--out", default="/tmp/vithia-space-live-demo/ACCEPTANCE_RECEIPT.json")
    ap.add_argument("--allow-2p-blocked", action="store_true")
    a = ap.parse_args()

    models = req(a.url, "/api/models").get("models", [])
    enabled = [m["name"] for m in models if m.get("enabled") and m["name"] != "SCRIPTED_BASELINE"]
    ollama = [m for m in enabled if m != "OPENJEV_TARGETED_EXPLORATORY"]
    if not ollama:
        raise SystemExit("no enabled real Ollama model discovered")
    m1 = ollama[0]
    m2 = ollama[1] if len(ollama) > 1 else ollama[0]

    receipt = {
        "schema": "VITHIA_LIVE_DEMO_ACCEPTANCE_V1",
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "url": a.url, "models_seen": models, "integrations": req(a.url, "/api/integrations"),
        "one_player": {}, "two_player": {}, "overall": "NOT_RUN",
    }

    # 1P: actual model, preprocessor, single step, play, pause, stop.
    req(a.url, "/api/config", {
        "mode": "1P", "model_a": m1, "model_b": m2, "seed": 3,
        "preprocessor": True, "backtrace": 6, "forecast": 6, "speed": "MODEL_PACED",
    })
    s0 = req(a.url, "/api/state")
    req(a.url, "/api/step", {})
    s1 = req(a.url, "/api/state")
    if s1["step"] != s0["step"] + 1 or not s1.get("frame"):
        raise SystemExit("1P STEP ONCE failed")
    req(a.url, "/api/play", {})
    s2 = wait_step(a.url, s1["step"])
    req(a.url, "/api/pause", {})
    p0 = req(a.url, "/api/state")["step"]
    time.sleep(.8)
    p1 = req(a.url, "/api/state")["step"]
    if p0 != p1:
        raise SystemExit("1P PAUSE did not freeze")
    req(a.url, "/api/stop", {})
    receipt["one_player"] = {
        "state": "PASS", "model": m1, "preprocessor": "A5_VITA01_FULL",
        "step_after_single": s1["step"], "step_after_play": s2["step"],
        "frame_sha256": s2.get("frame", {}).get("sha256"),
        "history_rows": len(s2.get("history", [])),
    }

    # 2P: code must either execute under an operator-supplied legal ROM gate or
    # report the explicit gate. No acquisition/bypass is performed here.
    req(a.url, "/api/config", {
        "mode": "2P", "model_a": m1, "model_b": m2, "seed": 3,
        "preprocessor": True, "backtrace": 6, "forecast": 6, "speed": "MODEL_PACED",
    })
    z0 = req(a.url, "/api/state")
    if z0.get("blocked"):
        receipt["two_player"] = {
            "state": z0["blocked"].get("state", "BLOCKED"),
            "reason": z0["blocked"].get("reason"),
            "executed": False,
        }
    else:
        req(a.url, "/api/step", {})
        z1 = req(a.url, "/api/state")
        if z1["step"] != 1 or not z1.get("frame"):
            raise SystemExit("2P STEP ONCE failed")
        req(a.url, "/api/play", {})
        z2 = wait_step(a.url, 1)
        req(a.url, "/api/pause", {})
        receipt["two_player"] = {
            "state": "PASS", "executed": True, "models": [m1, m2],
            "step": z2["step"], "scores": z2["score"],
            "frame_sha256": z2.get("frame", {}).get("sha256"),
        }

    two_ok = receipt["two_player"].get("state") == "PASS"
    receipt["overall"] = "PASS" if two_ok else ("PASS_WITH_EXPLICIT_2P_BLOCK" if a.allow_2p_blocked else "FAIL_2P_NOT_EXECUTED")
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps(receipt, indent=2))
    if receipt["overall"] not in ("PASS", "PASS_WITH_EXPLICIT_2P_BLOCK"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
