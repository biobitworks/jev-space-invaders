#!/usr/bin/env python3
"""Play fixed-seed games; after EACH game append to results.json, commit, push.

  python scripts/run_games.py --decider scripted --seeds 1 2 3 4 5
  python scripts/run_games.py --decider openjev --base-url http://127.0.0.1:3000 --seeds 1 2 3 4 5
  python scripts/run_games.py --decider jev --seeds 1 2 3 4 5            # needs TYPESAFE_API_KEY
  python scripts/run_games.py --decider llm --provider anthropic --model claude-haiku-4-5 --seeds 1 2 3 4 5
  python scripts/run_games.py --decider ollama --model qwen2.5:0.5b --seeds 1 2 3 4 5

Dry run (no git, separate file): add --dry-run --results /tmp/results.json
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.deciders import AdapterLLMDecider, ScriptedDecider, SystemOneHTTPDecider  # noqa: E402
from src.harness import preflight_git, record_run, run_episode  # noqa: E402


def load_dotenv() -> None:
    import os
    p = ROOT / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--decider", required=True, choices=["scripted", "jev", "openjev", "llm", "ollama"])
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3, 4, 5])
    ap.add_argument("--base-url")
    ap.add_argument("--provider", help="llm provider: openai | anthropic | gemini")
    ap.add_argument("--model")
    ap.add_argument("--max-steps", type=int)
    ap.add_argument("--note", help="short line per run: what changed and why")
    ap.add_argument("--results", default=str(ROOT / "results.json"))
    ap.add_argument("--branch", help="branch to push runs to (default: the repo default branch)")
    ap.add_argument("--dry-run", action="store_true", help="no git; requires --results outside the repo root file")
    a = ap.parse_args()
    load_dotenv()

    results = Path(a.results).resolve()
    if a.dry_run:
        if results == (ROOT / "results.json").resolve():
            raise SystemExit("--dry-run must write to a separate --results file")
        if not results.exists():
            shutil.copy(ROOT / "results.json", results)
    else:
        preflight_git(a.branch)

    if a.decider == "scripted":
        dec = ScriptedDecider()
    elif a.decider == "jev":
        dec = SystemOneHTTPDecider("typesafe", a.base_url, a.model)
    elif a.decider == "openjev":
        dec = SystemOneHTTPDecider("openjev", a.base_url, a.model)
    elif a.decider == "ollama":
        model = a.model or os.environ.get("OLLAMA_BASELINE_MODEL", "qwen2.5:0.5b")
        base_url = a.base_url or os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1")
        dec = AdapterLLMDecider("ollama", model, base_url=base_url)
    else:
        if not (a.provider and a.model):
            raise SystemExit("--decider llm needs --provider and --model")
        dec = AdapterLLMDecider(a.provider, a.model)

    for seed in a.seeds:
        print(f"== {a.decider} seed {seed}", flush=True)
        run, trace = run_episode(dec, seed, a.max_steps)
        out = record_run(run, trace, dec, results, push=not a.dry_run, note=a.note)
        keep = ("run", "seed", "score", "steps", "frames", "lives_lost", "model_calls",
                "latency_ms_p50", "latency_ms_p95", "mean_confidence", "fallback_actions",
                "served_model", "_pushed_commit")
        print(json.dumps({k: out[k] for k in keep if k in out}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
