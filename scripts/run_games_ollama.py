#!/usr/bin/env python3
"""Play fixed-seed games with a local-Ollama LLM baseline (no hosted provider key needed);
after EACH game append to results.json, commit, push. Companion to run_games.py's
`--decider llm` path, used when no TYPESAFE_API_KEY / cloud LLM key is available.
NOT the System One adapter (openai|anthropic|gemini) path: provider="ollama",
no calibrated probabilities. See src/ollama_baseline_decider.py.

  python scripts/run_games_ollama.py --model llama3.2:3b --seeds 1 2 3 4 5

Dry run (no git, separate file): add --dry-run --results /tmp/results.json
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.harness import preflight_git, record_run, run_episode  # noqa: E402
from src.ollama_baseline_decider import OllamaBaselineDecider  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="llama3.2:3b")
    ap.add_argument("--base-url", default="http://127.0.0.1:11434")
    ap.add_argument("--seeds", type=int, nargs="+", default=[1, 2, 3, 4, 5])
    ap.add_argument("--max-steps", type=int)
    ap.add_argument("--note", help="short line per run: what changed and why")
    ap.add_argument("--results", default=str(ROOT / "results.json"))
    ap.add_argument("--branch", help="branch to push runs to (default: the repo default branch)")
    ap.add_argument("--dry-run", action="store_true", help="no git; requires --results outside the repo root file")
    a = ap.parse_args()

    results = Path(a.results).resolve()
    if a.dry_run:
        if results == (ROOT / "results.json").resolve():
            raise SystemExit("--dry-run must write to a separate --results file")
        if not results.exists():
            shutil.copy(ROOT / "results.json", results)
    else:
        preflight_git(a.branch)

    dec = OllamaBaselineDecider(a.model, a.base_url)

    for seed in a.seeds:
        print(f"== ollama-baseline seed {seed}", flush=True)
        run, trace = run_episode(dec, seed, a.max_steps)
        out = record_run(run, trace, dec, results, push=not a.dry_run, note=a.note)
        keep = ("run", "seed", "score", "steps", "frames", "lives_lost", "model_calls",
                "latency_ms_p50", "latency_ms_p95", "mean_confidence", "fallback_actions",
                "served_model", "_pushed_commit")
        print(json.dumps({k: out[k] for k in keep if k in out}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
