#!/usr/bin/env python3
"""Discover every usable LOCAL decision-capable model/runtime already present and pick Doctor3 lanes from what exists.

Read-only and loopback-only: GET requests to 127.0.0.1 endpoints, `ollama --version`, and the repository's own
`scripts/openjev_runtime.py status`. It never downloads a model, never starts an unidentified service, and never sends
credentials anywhere. Starting the OpenJEV runtime is opt-in (start_openjev=True) and only uses already-present weights.
Ollama and Ollarma are reported separately and never collapsed into one label.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLLAMA_BASE = "http://127.0.0.1:11434"
FAMILIES = [("liquid", r"liquid|lfm"), ("qwen", r"qwen"), ("llama", r"llama"), ("granite", r"granite"), ("deepseek", r"deepseek"), ("phi", r"\bphi|/phi|^phi"),
            ("gemma", r"gemma"), ("mistral", r"mistral|mixtral"), ("smollm", r"smollm"), ("olmo", r"olmo")]


def _get(url: str, timeout: float = 5.0):
    with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": "application/json"}), timeout=timeout) as r:
        return r.status, json.loads(r.read())


def _post(url: str, body: dict, timeout: float = 10.0):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, json.loads(r.read())


def is_cloud(m: dict) -> bool:
    n = m.get("name", "")
    return bool(m.get("remote_host") or m.get("remote_model")) or ":cloud" in n or n.endswith("-cloud")


def family_of(name: str) -> str:
    low = name.lower()
    for fam, pat in FAMILIES:
        if re.search(pat, low):
            return fam
    return re.split(r"[:/\-_.]", low.replace("hf.co/", ""))[0] or "unknown"


def _model_rows(runtime: str, endpoint: str, tags: list[dict], probe_caps: bool) -> list[dict]:
    rows = []
    for m in tags:
        caps = None
        if probe_caps:
            try:
                _, info = _post(endpoint + "/api/show", {"model": m["name"]}, 10)
                caps = info.get("capabilities")
            except Exception:  # noqa: BLE001
                caps = None
        embed_only = (caps is not None and "completion" not in caps) or (caps is None and "embed" in m["name"].lower())
        rows.append({"runtime": runtime, "endpoint": endpoint, "name": m["name"], "size": m.get("size"), "local": not is_cloud(m),
                     "classification": "cloud/remote" if is_cloud(m) else "local", "capabilities": caps, "embedding_only": embed_only,
                     "available": True, "family": family_of(m["name"])})
    return rows


def discover_ollama(base: str = OLLAMA_BASE) -> dict:
    out = {"status": "NOT_FOUND", "endpoint": base, "binary": shutil.which("ollama") or "NOT_FOUND", "version": None, "models": [], "list_count": None}
    if out["binary"] != "NOT_FOUND":
        p = subprocess.run(["ollama", "--version"], capture_output=True, text=True)
        out["version"] = ((p.stdout or p.stderr).strip().splitlines() or [None])[0]
        lp = subprocess.run(["ollama", "list"], capture_output=True, text=True)
        out["list_count"] = max(0, len(lp.stdout.strip().splitlines()) - 1) if lp.returncode == 0 else None
    try:
        _, d = _get(base + "/api/tags")
        out["status"] = "RUNNING"
        out["models"] = _model_rows("ollama", base, d.get("models", []), probe_caps=True)
    except Exception as e:  # noqa: BLE001
        out["status"] = f"BINARY_PRESENT_SERVER_DOWN:{type(e).__name__}" if out["binary"] != "NOT_FOUND" else "NOT_FOUND"
    return out


def discover_ollarma(env: dict | None = None) -> dict:
    """Ollarma = the Watchtower FastAPI service (default :8000). Identified only by GET /api/ollarma/bridge-status."""
    env = env or os.environ
    port = int(env.get("WATCHTOWER_PORT", "8000"))
    base = f"http://127.0.0.1:{port}"
    out = {"status": "NOT_RUNNING", "endpoint": base, "models": [], "ollama_compatible_api": "NOT_TESTED", "project_dirs": []}
    for root in (Path.home() / ".ollarma", Path.home() / "ollarma"):
        if root.exists():
            out["project_dirs"].append("~/" + str(root.relative_to(Path.home())))
    try:
        code, d = _get(base + "/api/ollarma/bridge-status")
        out["status"] = "RUNNING_IDENTIFIED_BY_BRIDGE_STATUS" if code == 200 else f"UNIDENTIFIED_HTTP_{code}"
        out["bridge_status_keys"] = sorted(d)[:12] if isinstance(d, dict) else []
    except Exception as e:  # noqa: BLE001
        out["status"] = "NOT_RUNNING" if "refused" in str(e).lower() or "Connection" in type(e).__name__ else f"UNIDENTIFIED_LISTENER_OR_UNREACHABLE:{type(e).__name__}"
        return out
    try:
        _, t = _get(base + "/api/tags")
        if isinstance(t, dict) and isinstance(t.get("models"), list):
            out["ollama_compatible_api"] = "YES"
            out["models"] = _model_rows("ollarma", base, t["models"], probe_caps=False)
        else:
            out["ollama_compatible_api"] = "NO"
    except Exception as e:  # noqa: BLE001
        out["ollama_compatible_api"] = f"NO:{type(e).__name__}"
    return out


def discover_openjev(start: bool = False, timeout: int = 1200) -> dict:
    """Authoritative endpoint = the repository helper's recorded state; no port is ever guessed."""
    def status():
        p = subprocess.run([sys.executable, "scripts/openjev_runtime.py", "status"], cwd=ROOT, capture_output=True, text=True)
        if p.returncode != 0:
            return None
        try:
            return json.loads(p.stdout)
        except Exception:
            return None
    st = status()
    out = {"status": "NOT_RUNNING", "endpoint": None, "started_by_this_run": False}
    if st and st.get("alive"):
        out.update(status="RUNNING_IDENTIFIED_BY_REPO_HELPER", endpoint=f"http://127.0.0.1:{st['port']}")
        return out
    if st and not st.get("alive"):
        out["status"] = "NOT_RUNNING_STALE_STATE"
    weights = Path(os.environ.get("OPENJEV_HOME", Path.home() / ".openjev")) / "openjev-MLX-4bit"
    if not start:
        out["startable_from_existing_weights"] = weights.exists() and any(weights.iterdir()) if weights.exists() else False
        return out
    if not (weights.exists() and any(weights.iterdir())):
        out["status"] = "NOT_AVAILABLE_NO_EXISTING_RUNTIME"
        return out
    p = subprocess.run([sys.executable, "scripts/openjev_runtime.py", "serve"], cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    st = status()
    if p.returncode == 0 and st and st.get("alive"):
        out.update(status="RUNNING_IDENTIFIED_BY_REPO_HELPER", endpoint=f"http://127.0.0.1:{st['port']}", started_by_this_run=True)
    else:
        out.update(status="START_FAILED", detail=(p.stdout + p.stderr)[-300:].replace(str(Path.home()), "~"))
    return out


def usable(models: list[dict]) -> list[dict]:
    """Local, decision-capable, deduplicated by model name (an Ollama copy wins over an Ollarma copy). No family exclusions."""
    seen, out = {}, []
    for m in sorted(models, key=lambda m: (0 if m["runtime"] == "ollama" else 1, m["name"])):
        if not m["local"] or m["embedding_only"] or not m["available"] or m["name"] in seen:
            continue
        seen[m["name"]] = True
        out.append(m)
    return out


def select_lanes(models: list[dict], limit: int = 4) -> list[dict]:
    """Diversity across families; Liquid first if present, then Qwen (qwen3 preferred), then the smallest of each other family,
    then a second variant of an already-chosen family only if slots remain. Deterministic: ties break on (size, name)."""
    pool = usable(models)
    key = lambda m: (m["size"] if m["size"] is not None else 1 << 60, m["name"])
    by_fam: dict[str, list[dict]] = {}
    for m in sorted(pool, key=key):
        by_fam.setdefault(m["family"], []).append(m)
    chosen: list[dict] = []
    def take(m):
        if m and m not in chosen and len(chosen) < limit:
            chosen.append(m)
    if "liquid" in by_fam:
        take(by_fam["liquid"][0])
    if "qwen" in by_fam:
        q3 = [m for m in by_fam["qwen"] if m["name"].lower().startswith("qwen3")]
        take((q3 or by_fam["qwen"])[0])
    for fam in sorted((f for f in by_fam if f not in {c["family"] for c in chosen}), key=lambda f: key(by_fam[f][0])):
        take(by_fam[fam][0])
    for fam in [c["family"] for c in list(chosen)]:                       # too few families: allow a second variant
        for m in by_fam[fam]:
            take(m)
    return chosen


def lane_spec(chosen: list[dict], openjev: dict | None = None) -> str:
    toks = ["scripted"] + [f"{m['runtime']}:{m['name']}" for m in chosen]
    if openjev and openjev.get("status", "").startswith("RUNNING_IDENTIFIED"):
        toks.append("openjev")
    return ",".join(toks)


def discover_all(start_openjev: bool = False) -> dict:
    ol, oa, oj = discover_ollama(), discover_ollarma(), discover_openjev(start_openjev)
    every = ol["models"] + oa["models"]
    chosen = select_lanes(every)
    return {"ollama": ol, "ollarma": oa, "openjev": oj, "all_models": every, "usable": usable(every), "chosen": chosen, "lanes": lane_spec(chosen, oj)}


if __name__ == "__main__":
    d = discover_all(start_openjev="--start-openjev" in sys.argv)
    print(json.dumps({k: (v if k not in ("all_models", "usable") else [{x: m[x] for x in ("runtime", "name", "size", "classification", "embedding_only", "family")} for m in v]) for k, v in d.items()}, indent=1))
