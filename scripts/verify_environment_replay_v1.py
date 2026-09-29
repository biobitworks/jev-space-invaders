#!/usr/bin/env python3
"""Deterministically replay a recorded 1P ALE run from its frozen action stream.

This verifier never rewrites historical evidence and never uses recorded images as
generated observations. It verifies trace bytes/MMR first, then regenerates the
environment trajectory from seed + recorded actions and reports the first mismatch.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.actions import ACTION_TO_ID
from src.envcfg import ENV_CONFIG, make_env, runtime_versions
from src.fmo import hp, mmr_root
from src.perception import Perception
from src.s01.canon import content_id


def load_results(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def all_runs(results: dict) -> list[dict]:
    return list(results.get("runs", [])) + list(results.get("baseline", {}).get("runs", []))


def find_run(results: dict, run_number: int) -> dict:
    for run in all_runs(results):
        if int(run.get("run", -1)) == run_number:
            return run
    raise SystemExit(f"run {run_number} not found")


def load_trace(results_path: Path, run: dict) -> tuple[Path, list[dict], str]:
    trace_path = (results_path.parent / run["trace_file"]).resolve()
    if not trace_path.exists():
        raise SystemExit(f"trace missing: {trace_path}")
    sha = hashlib.sha256(trace_path.read_bytes()).hexdigest()
    with gzip.open(trace_path, "rt", encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh if line.strip()]
    return trace_path, rows, sha


def trace_leaf(row: dict) -> str:
    t = int(row["t"])
    body = {k: v for k, v in row.items() if k not in ("leaf", "ms")}
    return hp("EPISODE_LEAF_V1", t, content_id(body)).hex()


def verify_trace(run: dict, rows: list[dict], trace_sha: str) -> dict:
    first = None
    if trace_sha != run.get("trace_sha256"):
        first = {
            "kind": "TRACE_SHA256",
            "expected": run.get("trace_sha256"),
            "observed": trace_sha,
        }

    leaves = []
    leaf_errors = []
    for i, row in enumerate(rows):
        got = trace_leaf(row)
        want = row.get("leaf")
        if got != want:
            leaf_errors.append({"t": i, "expected": want, "observed": got})
            if first is None:
                first = {"kind": "TRACE_LEAF", "t": i, "expected": want, "observed": got}
        if want:
            try:
                leaves.append(bytes.fromhex(want))
            except ValueError:
                if first is None:
                    first = {"kind": "TRACE_LEAF_HEX", "t": i, "observed": want}

    root, _ = mmr_root(leaves)
    if root != run.get("episode_mmr_root") and first is None:
        first = {
            "kind": "TRACE_MMR",
            "expected": run.get("episode_mmr_root"),
            "observed": root,
        }

    return {
        "trace_sha256_match": trace_sha == run.get("trace_sha256"),
        "leaf_hash_equality": "PASS" if not leaf_errors else "FAIL",
        "trace_rows": len(rows),
        "recorded_mmr_root": run.get("episode_mmr_root"),
        "recomputed_trace_mmr_root": root,
        "trace_mmr_equality": "PASS" if root == run.get("episode_mmr_root") else "FAIL",
        "first_trace_mismatch": first,
    }


def mismatch(kind: str, t: int, expected, observed) -> dict:
    return {"kind": kind, "t": t, "expected": expected, "observed": observed}


def replay(run: dict, rows: list[dict]) -> dict:
    env = make_env()
    perception = Perception()
    obs, info = env.reset(seed=int(run["seed"]))
    score = 0.0
    prev = "NOOP"
    first = None
    generated = 0
    term = trunc = False

    for i, row in enumerate(rows):
        if first is not None:
            break
        t = int(row["t"])
        if t != i:
            first = mismatch("STEP_INDEX", i, i, t)
            break

        state = perception.observe(
            obs,
            lives=int(info["lives"]),
            score=score,
            step=t,
            prev_action=prev,
        )
        sid = content_id(state)
        if sid != row.get("state_id"):
            first = mismatch("STATE_ID", t, row.get("state_id"), sid)
            break

        action = row.get("action")
        if action not in ACTION_TO_ID:
            first = mismatch("ACTION_ONTOLOGY", t, "known action", action)
            break

        obs, reward, term, trunc, info = env.step(ACTION_TO_ID[action])
        score += float(reward)
        generated += 1

        if float(reward) != float(row.get("reward", 0.0)):
            first = mismatch("REWARD", t, row.get("reward"), float(reward))
            break

        lives = int(info["lives"])
        if lives != int(row.get("lives")):
            first = mismatch("LIVES", t, row.get("lives"), lives)
            break

        frame_sha = hashlib.sha256(obs.tobytes()).hexdigest()
        if frame_sha != row.get("next_frame_sha256"):
            first = mismatch("NEXT_FRAME_SHA256", t, row.get("next_frame_sha256"), frame_sha)
            break

        prev = action

    final_frames = int(info.get("episode_frame_number", 0))
    env.close()

    if first is None and generated != len(rows):
        first = mismatch("ROW_COUNT", generated, len(rows), generated)
    if first is None and float(score) != float(run.get("score")):
        first = mismatch("FINAL_SCORE", generated, run.get("score"), score)
    if first is None and int(run.get("steps", len(rows))) != len(rows):
        first = mismatch("RECORDED_STEPS", generated, run.get("steps"), len(rows))
    if first is None and int(run.get("frames", final_frames)) != final_frames:
        first = mismatch("EPISODE_FRAME_NUMBER", generated, run.get("frames"), final_frames)
    if first is None and bool(run.get("terminated")) != bool(term):
        first = mismatch("TERMINATED", generated, run.get("terminated"), bool(term))

    return {
        "frames_expected": len(rows),
        "decisions_generated": generated,
        "first_mismatch": first,
        "score_observed": score,
        "score_expected": run.get("score"),
        "episode_frames_observed": final_frames,
        "episode_frames_expected": run.get("frames"),
        "terminated_observed": bool(term),
        "terminated_expected": bool(run.get("terminated")),
        "truncated_observed": bool(trunc),
        "runtime_versions_observed": runtime_versions(),
        "environment": ENV_CONFIG,
        "replay_from_start": "PASS" if first is None else "FAIL",
        "step_hash_equality": "PASS" if first is None else "FAIL",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=str(ROOT / "results.json"))
    ap.add_argument("--run", type=int, required=True)
    ap.add_argument("--out")
    args = ap.parse_args()

    results_path = Path(args.results).resolve()
    results = load_results(results_path)
    run = find_run(results, args.run)
    trace_path, rows, trace_sha = load_trace(results_path, run)
    trace_check = verify_trace(run, rows, trace_sha)

    if (
        trace_check["trace_sha256_match"]
        and trace_check["leaf_hash_equality"] == "PASS"
        and trace_check["trace_mmr_equality"] == "PASS"
    ):
        replay_check = replay(run, rows)
    else:
        replay_check = {
            "frames_expected": len(rows),
            "decisions_generated": 0,
            "first_mismatch": trace_check["first_trace_mismatch"],
            "replay_from_start": "NOT_EXECUTED_TRACE_INTEGRITY_FAIL",
            "step_hash_equality": "NOT_EXECUTED_TRACE_INTEGRITY_FAIL",
        }

    ok = (
        trace_check["trace_sha256_match"]
        and trace_check["leaf_hash_equality"] == "PASS"
        and trace_check["trace_mmr_equality"] == "PASS"
        and replay_check["replay_from_start"] == "PASS"
        and replay_check["step_hash_equality"] == "PASS"
    )

    receipt = {
        "schema": "ENVIRONMENT_REPLAY_VERIFICATION_RECEIPT_V1",
        "run": args.run,
        "seed": run.get("seed"),
        "provider": run.get("provider"),
        "requested_model": run.get("requested_model"),
        "served_model": run.get("served_model"),
        "trace_file": run.get("trace_file"),
        **trace_check,
        **replay_check,
        "final_mmr_equality": trace_check["trace_mmr_equality"],
        "environment_replay": "PASS" if ok else "FAIL",
        "claim_ceiling": (
            "DETERMINISTIC_REPLAY_OF_RECORDED_ACTION_STREAM_VERIFIED"
            if ok else
            "REPLAY_DIVERGENCE_PRESERVED_NO_REWRITE"
        ),
    }

    out = Path(args.out).resolve() if args.out else None
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
