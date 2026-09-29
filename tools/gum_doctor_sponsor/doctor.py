#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import urllib.request

ROOT = Path(__file__).resolve().parents[2]
PRIVATE = ROOT / ".private" / "sponsor-proof"
STATUS = PRIVATE / "gum_doctor_status.json"
KEYS = [
    "MI_API_KEY",
    "MITOSIS_API_KEY",
    "TENKI_API_KEY",
    "TENKI_AUTH_TOKEN",
    "TYPESAFE_API_KEY",
    "ANTHROPIC_API_KEY",
]

def run(*args: str) -> str | None:
    try:
        return subprocess.run(
            list(args), cwd=ROOT, text=True, capture_output=True,
            check=True, timeout=10,
        ).stdout.strip()
    except Exception:
        return None

def http_json(url: str) -> tuple[str, object | None]:
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            return "PASS", json.loads(response.read())
    except Exception as exc:
        return f"BLOCKED_{type(exc).__name__}", None

def main() -> None:
    PRIVATE.mkdir(parents=True, exist_ok=True)
    try:
        PRIVATE.chmod(0o700)
    except OSError:
        pass

    branch = run("git", "branch", "--show-current")
    head = run("git", "rev-parse", "HEAD")
    origin_main = run("git", "rev-parse", "origin/main")
    worktree = run("git", "status", "--porcelain")
    env_state = {key: ("SET" if os.getenv(key) else "NOT_SET") for key in KEYS}

    replay = ROOT / "evidence/competition/replay_seed_adaptive/run_openjev_vithia_l1_f71e267476ef/REPLAY_SEED_FCO.json"
    replay_state = "FOUND" if replay.exists() else "MISSING"

    ollama_base = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    ollama_state, ollama_payload = http_json(ollama_base + "/api/tags")
    ollama_models = []
    if isinstance(ollama_payload, dict):
        for row in ollama_payload.get("models", []):
            if isinstance(row, dict):
                name = row.get("name") or row.get("model")
                if name:
                    ollama_models.append(name)

    openjev_endpoint = None
    runtime_manifest = ROOT / "evidence/openjev/RUNTIME_MANIFEST.json"
    if runtime_manifest.exists():
        try:
            openjev_endpoint = json.loads(runtime_manifest.read_text(encoding="utf-8")).get("endpoint")
        except Exception:
            pass
    openjev_endpoint = os.getenv("OPENJEV_BASE_URL") or openjev_endpoint
    openjev_state = "NOT_CONFIGURED"
    if openjev_endpoint:
        try:
            req = urllib.request.Request(openjev_endpoint, method="GET")
            with urllib.request.urlopen(req, timeout=3):
                openjev_state = "REACHABLE"
        except Exception as exc:
            # A 404/405 still proves that a listener answered; preserve only class.
            openjev_state = f"PROBED_{type(exc).__name__}"

    report = {
        "HOST": run("hostname"),
        "BRANCH": branch,
        "HEAD": head,
        "ORIGIN_MAIN": origin_main,
        "ORIGIN_PARITY": "PASS" if head and origin_main and head == origin_main else "DIFF",
        "WORKTREE": "CLEAN" if worktree == "" else "DIRTY",
        "SPONSOR_ENV": "LOADED" if any(v == "SET" for v in env_state.values()) else "NO_KEYS_SET",
        "KEYS": env_state,
        "CLAUDE_CLI": "AVAILABLE" if shutil.which("claude") else "NOT_FOUND_IN_PATH",
        "OLLARMA_DIR": "FOUND" if (Path.home() / "projects/active/ollarma").exists() else "NOT_FOUND",
        "OLLAMA": ollama_state,
        "OLLAMA_MODELS": ollama_models,
        "OPENJEV": openjev_state,
        "REPLAY_SEED": replay_state,
    }
    STATUS.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    try:
        STATUS.chmod(0o600)
    except OSError:
        pass

    print(f"HOST={report['HOST']}")
    print(f"BRANCH={branch}")
    print(f"HEAD={head}")
    print(f"ORIGIN_MAIN={origin_main}")
    print(f"ORIGIN_PARITY={report['ORIGIN_PARITY']}")
    print(f"WORKTREE={report['WORKTREE']}")
    print(f"SPONSOR_ENV={report['SPONSOR_ENV']}")
    for key in KEYS:
        print(f"{key}={env_state[key]}")
    print(f"CLAUDE_CLI={report['CLAUDE_CLI']}")
    print(f"OLLARMA_DIR={report['OLLARMA_DIR']}")
    print(f"OLLAMA={ollama_state}")
    print("OLLAMA_MODELS=" + (",".join(ollama_models) if ollama_models else "NONE"))
    print(f"OPENJEV={openjev_state}")
    print(f"REPLAY_SEED={replay_state}")
    print(f"SANITIZED_STATUS={STATUS}")

if __name__ == "__main__":
    main()
