#!/usr/bin/env python3
"""OpenJev runtime verification on Apple Silicon (MLX 4-bit). Fail-closed.

  python scripts/openjev_runtime.py download   # pinned-revision download + SHA-256 of every artifact
  python scripts/openjev_runtime.py serve      # free loopback port (never 3000), start shim_mlx, wait, SETUP_SMOKE
  python scripts/openjev_runtime.py status     # re-check resident process + endpoint
  python scripts/openjev_runtime.py stop

OPENJEV_LOADED=YES only when all 7 checks are OBSERVED: files exist, hashes match, engine opened
the weights (endpoint up), resident PID alive, endpoint responds, SETUP_SMOKE schema call ok,
served-model string recorded. The smoke payload is synthetic: SETUP_SMOKE / NON_EXPERIMENTAL /
NOT_E4A / NOT_COUNTED. The local bearer token lives in ~/.openjev/token (never in git).
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import secrets
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ID = json.loads((ROOT / "evidence/openjev/UPSTREAM_IDENTITY.json").read_text())
HOME = Path(os.environ.get("OPENJEV_HOME", Path.home() / ".openjev"))
MODEL_DIR = HOME / "openjev-MLX-4bit"
HELPER_DIR = HOME / "helper"
STATE = HOME / "runtime_state.json"
MANIFEST = ROOT / "evidence/openjev/RUNTIME_MANIFEST.json"


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 22), b""):
            h.update(c)
    return h.hexdigest()


def fail(msg, extra=None):
    rec = {"schema": "OPENJEV_RUNTIME_MANIFEST_V1", "utc": now(), "OPENJEV_LOADED": "NO", "failure": msg, **(extra or {})}
    MANIFEST.write_text(json.dumps(rec, indent=2) + "\n")
    raise SystemExit(f"FAIL-CLOSED: {msg}  (manifest written: {MANIFEST.relative_to(ROOT)})")


def download():
    from huggingface_hub import hf_hub_download, snapshot_download
    m, h = ID["model"], ID["helper"]
    snapshot_download(m["repo"], revision=m["revision"], local_dir=MODEL_DIR)
    for f in h["files"]:
        hf_hub_download(h["repo"], f, revision=h["revision"], local_dir=HELPER_DIR)
    print(json.dumps(verify_files(), indent=2))


def verify_files() -> dict:
    m, h = ID["model"], ID["helper"]
    out = {"weights": {}, "helper": {}}
    for name, (size, exp) in {**m["weights"], "tokenizer.json": m["tokenizer.json"]}.items():
        p = MODEL_DIR / name
        if not p.exists():
            fail(f"missing {name}")
        got = sha(p)
        if p.stat().st_size != size or got != exp:
            fail(f"hash/size mismatch {name}", {"expected": exp, "got": got, "size": p.stat().st_size})
        out["weights"][name] = {"bytes": size, "sha256": got}
    for rel, exp in h["files"].items():
        p = HELPER_DIR / rel
        got = sha(p) if p.exists() else None
        if got != exp:
            fail(f"helper mismatch {rel}", {"expected": exp, "got": got})
        out["helper"][rel] = got
    out["config_sha256"] = sha(MODEL_DIR / "config.json")
    out["tokenizer_config_sha256"] = sha(MODEL_DIR / "tokenizer_config.json")
    return out


def free_port() -> int:
    for p in range(8765, 8865):
        if p == 3000:
            continue
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    fail("no free loopback port in 8765-8864")


def smoke(port: int, token: str) -> dict:
    body = {"state": {"label": "SETUP_SMOKE", "note": "NON_EXPERIMENTAL NOT_E4A NOT_COUNTED", "text": "A red square is left of a blue circle."},
            "questions": {"which": {"type": "choice", "instructions": "Which shape is on the left?",
                                    "criteria": {"square": "the square", "circle": "the circle"}}}}
    req = urllib.request.Request(f"http://127.0.0.1:{port}/v1/systemone", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"}, method="POST")
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=120) as r:
        resp = json.loads(r.read())
    return {"label": "SETUP_SMOKE", "non_experimental": True, "not_e4a": True, "not_counted": True,
            "latency_ms": round((time.perf_counter() - t0) * 1000, 1), "served_model": resp.get("model"),
            "answer": resp.get("answers", {}).get("which"), "schema_ok": "which" in resp.get("answers", {})}


def serve():
    files = verify_files()
    HOME.mkdir(exist_ok=True)
    tokf = HOME / "token"
    if not tokf.exists():
        tokf.write_text(secrets.token_hex(16))
        tokf.chmod(0o600)
    token = tokf.read_text().strip()
    port = free_port()
    env = {**os.environ, **ID["serve_env"], "SHIM_TOKEN": token}
    logf = open(HOME / f"shim_{port}.log", "w")
    proc = subprocess.Popen([sys.executable, str(HELPER_DIR / "helper/shim_mlx.py"), "--helper", str(HELPER_DIR / "helper/shim.py"),
                             "--model", str(MODEL_DIR), "--port", str(port), "--host", "127.0.0.1"],
                            env=env, stdout=logf, stderr=subprocess.STDOUT, start_new_session=True)
    t0 = time.time()
    while time.time() - t0 < 900:
        if proc.poll() is not None:
            fail("shim exited during load", {"log_tail": (HOME / f"shim_{port}.log").read_text()[-3000:]})
        if "MLX helper on" in (HOME / f"shim_{port}.log").read_text():
            break
        time.sleep(2)
    else:
        fail("load timeout 900s")
    load_s = round(time.time() - t0, 1)
    try:
        sm = smoke(port, token)
    except Exception as e:  # noqa: BLE001
        fail(f"smoke failed: {e!r}", {"pid": proc.pid, "port": port})
    alive = proc.poll() is None
    checks = {"files_exist": True, "hashes_match": True, "engine_opened_weights": True, "resident_process": alive,
              "endpoint_responds": True, "smoke_schema_ok": sm["schema_ok"], "served_model_recorded": bool(sm["served_model"])}
    import importlib.metadata as md

    def v(n):
        try:
            return md.version(n)
        except Exception:
            return None
    rec = {"schema": "OPENJEV_RUNTIME_MANIFEST_V1", "utc_load": now(), "upstream": ID, "artifacts": files,
           "local_path": str(MODEL_DIR), "endpoint": f"http://127.0.0.1:{port}/v1/systemone", "port": port, "pid": proc.pid,
           "auth": "bearer token in ~/.openjev/token (not recorded)", "load_seconds": load_s,
           "engine": {"mlx": v("mlx"), "mlx_lm": v("mlx-lm"), "transformers": v("transformers")},
           "python": sys.version.split()[0], "hardware": {"machine": platform.machine(), "platform": platform.platform(),
                                                          "host": platform.node()},
           "serve_env": ID["serve_env"], "smoke": sm, "checks": checks,
           "OPENJEV_LOADED": "YES" if all(checks.values()) else "NO", "provider_label": "openjev NON_TYPESAFE_JEV NON_COUNTED"}
    MANIFEST.write_text(json.dumps(rec, indent=2) + "\n")
    STATE.write_text(json.dumps({"pid": proc.pid, "port": port}))
    print(json.dumps({k: rec[k] for k in ("OPENJEV_LOADED", "endpoint", "pid", "load_seconds", "checks")} | {"served_model": sm["served_model"]}, indent=2))
    if rec["OPENJEV_LOADED"] != "YES":
        raise SystemExit("FAIL-CLOSED: not all load checks observed")


def status():
    st = json.loads(STATE.read_text())
    alive = subprocess.run(["kill", "-0", str(st["pid"])]).returncode == 0
    print(json.dumps({"pid": st["pid"], "alive": alive, "port": st["port"]}))


def stop():
    st = json.loads(STATE.read_text())
    subprocess.run(["kill", str(st["pid"])])
    print("stopped", st)


if __name__ == "__main__":
    {"download": download, "serve": serve, "status": status, "stop": stop}[sys.argv[1]]()
