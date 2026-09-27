"""Episode loop, measurement, and per-game results.json + git push.

Every number written comes from the environment, the API response, or a clock in
this process. A run that fails to push stops the session: the next game must not
start until the previous one is on the default branch.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import subprocess
import time
from pathlib import Path

import numpy as np

from src.actions import ACTION_TO_ID
from src.envcfg import ENV_CONFIG, make_env, runtime_versions
from src.perception import VERSION as PERCEPTION_VERSION, Perception
from src.validate import check

ROOT = Path(__file__).resolve().parents[1]
LOW_CONF = 0.6


def run_episode(decider, seed: int, max_steps: int | None = None, log_every: int = 500) -> tuple[dict, list]:
    env = make_env()
    perception = Perception()
    obs, info = env.reset(seed=seed)
    lives0 = int(info["lives"])
    score, steps, prev = 0.0, 0, "NOOP"
    lat, confs, trace = [], [], []
    calls = in_tok = out_tok = retries = fallbacks = 0
    tok_seen = False
    errors: dict[str, int] = {}
    served: set[str] = set()
    term = trunc = capped = False
    t_start = time.perf_counter()
    while True:
        state = perception.observe(obs, lives=int(info["lives"]), score=score, step=steps, prev_action=prev)
        t0 = time.perf_counter()
        d = decider.decide(state, prev)
        ms = (time.perf_counter() - t0) * 1000.0
        lat.append(ms)
        if d.model_call:
            calls += 1
        if d.input_tokens is not None:
            in_tok += d.input_tokens
            tok_seen = True
        if d.output_tokens is not None:
            out_tok += d.output_tokens
        retries += d.retries
        fallbacks += int(d.fallback)
        for k, v in d.errors.items():
            errors[k] = errors.get(k, 0) + v
        if d.confidence is not None:
            confs.append(float(d.confidence))
        if d.served_model:
            served.add(d.served_model)
        obs, r, term, trunc, info = env.step(ACTION_TO_ID[d.action])
        score += float(r)
        trace.append({"t": steps, "action": d.action, "proposed": d.proposed_action,
                      "conf": d.confidence, "p": d.probabilities, "ms": round(ms, 2),
                      "reward": float(r), "lives": int(info["lives"]),
                      "ship_x": (state["ship"] or {}).get("x"), "n_bombs": len(state["bombs"]),
                      "fallback": d.fallback_reason})
        steps += 1
        prev = d.action
        if log_every and steps % log_every == 0:
            print(f"  seed {seed} step {steps} score {score:.0f} lives {info['lives']}", flush=True)
        if term or trunc:
            break
        if max_steps and steps >= max_steps:
            capped = True
            break
    env.close()
    a = np.array(lat)
    run = {
        "seed": seed, "score": score, "steps": steps,
        "frames": int(info["episode_frame_number"]),
        "lives_lost": lives0 - int(info["lives"]),
        "terminated": bool(term), "truncated": bool(trunc or capped),
        "model_calls": calls,
        "latency_ms_p50": round(float(np.percentile(a, 50)), 3),
        "latency_ms_p95": round(float(np.percentile(a, 95)), 3),
        "latency_ms_total": round(float(a.sum()), 3),
        "errors_by_status": errors, "retries": retries, "fallback_actions": fallbacks,
        "wall_clock_s": round(time.perf_counter() - t_start, 2),
        "served_model": ",".join(sorted(served)) if served else None,
        "provider": decider.provider, "requested_model": decider.requested_model,
        "state_encoding": PERCEPTION_VERSION,
        "runtime": runtime_versions(),
    }
    if tok_seen:
        run["input_tokens"], run["output_tokens"] = in_tok, out_tok
    if confs:
        c = np.array(confs)
        run["mean_confidence"] = round(float(c.mean()), 4)
        run["low_conf_rate"] = round(float((c < LOW_CONF).mean()), 4)
    if capped:
        run["max_steps_cap"] = max_steps
    return run, trace


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)


def preflight_git() -> str:
    br = _git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    default = _git("symbolic-ref", "--short", "refs/remotes/origin/HEAD").stdout.strip().split("/")[-1] or "main"
    if br != default:
        raise SystemExit(f"On branch {br}; judges read {default}. Switch to {default} before counted runs.")
    dirty = [l for l in _git("status", "--porcelain").stdout.splitlines() if l.strip()]
    if dirty:
        raise SystemExit("Worktree not clean; commit or stash first:\n" + "\n".join(dirty))
    return br


def record_run(run: dict, trace: list, decider, results_path: Path, push: bool, note: str | None) -> dict:
    d = json.loads(results_path.read_text())
    cfg = d.setdefault("config", {})
    cfg.update({k: v for k, v in ENV_CONFIG.items()})
    cfg["ale_py_version"] = run["runtime"]["ale_py"]
    cfg["gymnasium_version"] = run["runtime"]["gymnasium"]
    cfg["state_encoding"] = f"{PERCEPTION_VERSION}: RGB frame parsed to ship, bombs, shots, aliens, shields as JSON (no raw RAM)"
    if run.get("max_steps_cap"):
        cfg["max_steps"] = run["max_steps_cap"]

    model_entry = {"role": decider.role, "provider": decider.provider,
                   "requested_model": decider.requested_model, "served_model": run["served_model"],
                   "sdk_package": decider.sdk_package, "sdk_version": decider.sdk_version}
    models = d.setdefault("models", [])
    if not any(m.get("role") == model_entry["role"] and m.get("served_model") == model_entry["served_model"]
               and m.get("provider") == model_entry["provider"] for m in models):
        models.append(model_entry)

    n = len(d.get("runs", [])) + len(d.get("baseline", {}).get("runs", [])) + 1
    run = {"run": n, **run}
    if note:
        run["notes"] = note
    runs_dir = results_path.parent / "runs"
    runs_dir.mkdir(exist_ok=True)
    tpath = runs_dir / f"run_{n:04d}_seed{run['seed']}_{run['provider']}.jsonl.gz"
    raw = "".join(json.dumps(x, separators=(",", ":")) + "\n" for x in trace).encode()
    tpath.write_bytes(gzip.compress(raw, mtime=0))
    run["trace_file"] = str(tpath.relative_to(results_path.parent))
    run["trace_sha256"] = hashlib.sha256(tpath.read_bytes()).hexdigest()

    if decider.role == "baseline":
        bl = d.setdefault("baseline", {"model": None, "runs": []})
        bl["model"] = run["served_model"] or decider.requested_model
        bl["runs"].append(run)
    else:
        d.setdefault("runs", []).append(run)
    check(d)  # refuse to write/push numbers that do not add up
    results_path.write_text(json.dumps(d, indent=2) + "\n")

    if push:
        for cmd in (["add", str(results_path), str(tpath)],
                    ["commit", "-m", f"results: run {n}, score {int(run['score'])}"],
                    ["push"]):
            p = _git(*cmd)
            if p.returncode != 0:
                raise SystemExit(f"git {' '.join(cmd)} failed; stopping before next game.\n{p.stderr}")
        run["_pushed_commit"] = _git("rev-parse", "HEAD").stdout.strip()
    return run
