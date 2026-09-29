#!/usr/bin/env python3
"""Determine objective evaluation/match outcomes from verified recorded evidence.

No model narrative or video interpretation is used. Historical evidence is read-only.
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

from src.fmo import hp, mmr_root
from src.s01.canon import content_id


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def rows_from_gzip(path: Path) -> list[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def recompute_episode(rows: list[dict]) -> tuple[str, list[dict]]:
    leaves = []
    errors = []
    for i, row in enumerate(rows):
        body = {k: v for k, v in row.items() if k not in ("leaf", "ms")}
        got = hp("EPISODE_LEAF_V1", int(row["t"]), content_id(body)).hex()
        want = row.get("leaf")
        if got != want:
            errors.append({"t": i, "expected": want, "observed": got})
        if want:
            try:
                leaves.append(bytes.fromhex(want))
            except ValueError:
                errors.append({"t": i, "kind": "INVALID_LEAF_HEX", "observed": want})
    root, _ = mmr_root(leaves)
    return root, errors


def all_runs(results: dict) -> list[dict]:
    return list(results.get("runs", [])) + list(results.get("baseline", {}).get("runs", []))


def run_by_number(results: dict, n: int) -> dict:
    for r in all_runs(results):
        if int(r.get("run", -1)) == n:
            return r
    raise SystemExit(f"run {n} not found")


def verify_1p_run(results_path: Path, run: dict) -> dict:
    trace = (results_path.parent / run["trace_file"]).resolve()
    if not trace.exists():
        return {"status": "FAIL", "blocker": "TRACE_MISSING", "trace": str(trace)}
    sha = hashlib.sha256(trace.read_bytes()).hexdigest()
    rows = rows_from_gzip(trace)
    root, errors = recompute_episode(rows)
    ok = (
        sha == run.get("trace_sha256")
        and not errors
        and root == run.get("episode_mmr_root")
        and len(rows) == int(run.get("episode_mmr_size", len(rows)))
    )
    return {
        "status": "PASS" if ok else "FAIL",
        "trace_sha256_match": sha == run.get("trace_sha256"),
        "leaf_errors": errors,
        "recomputed_mmr_root": root,
        "recorded_mmr_root": run.get("episode_mmr_root"),
        "row_count": len(rows),
    }


def compare_1p(args) -> dict:
    results_path = Path(args.results).resolve()
    results = read_json(results_path)
    left = run_by_number(results, args.left_run)
    right = run_by_number(results, args.right_run)
    lv = verify_1p_run(results_path, left)
    rv = verify_1p_run(results_path, right)

    blockers = []
    if lv["status"] != "PASS":
        blockers.append("LEFT_TRACE_NOT_VERIFIED")
    if rv["status"] != "PASS":
        blockers.append("RIGHT_TRACE_NOT_VERIFIED")
    if left.get("seed") != right.get("seed"):
        blockers.append("SEED_MISMATCH")

    if blockers:
        winner = "NOT_ESTABLISHED"
    else:
        ls, rs = float(left["score"]), float(right["score"])
        winner = "TIE" if ls == rs else ("LEFT" if ls > rs else "RIGHT")

    return {
        "schema": "DETERMINISTIC_GAME_OUTCOME_V1",
        "outcome_class": "ONE_PLAYER_EVALUATION_WINNER",
        "winner_predicate": "HIGHER_FINAL_CUMULATIVE_ENVIRONMENT_SCORE_SAME_SEED",
        "literal_game_win_claim": "NO",
        "left_run": args.left_run,
        "right_run": args.right_run,
        "seed": left.get("seed") if left.get("seed") == right.get("seed") else None,
        "left_score": left.get("score"),
        "right_score": right.get("score"),
        "left_model": left.get("served_model") or left.get("requested_model"),
        "right_model": right.get("served_model") or right.get("requested_model"),
        "left_trace_verify": lv,
        "right_trace_verify": rv,
        "winner": winner,
        "blockers": blockers,
        "claim_ceiling": "COMPARATIVE_EVALUATION_OUTCOME_ONLY_NOT_LITERAL_GAME_COMPLETION",
    }


def compare_2p(args) -> dict:
    summary_path = Path(args.summary).resolve()
    summary = read_json(summary_path)
    matchup = summary.get("matchup")
    candidates = [r for r in summary.get("runs", []) if int(r.get("seed", -1)) == args.seed]
    if len(candidates) != 1:
        return {
            "schema": "DETERMINISTIC_GAME_OUTCOME_V1",
            "outcome_class": "TWO_PLAYER_MATCH_WINNER",
            "winner": "NOT_ESTABLISHED",
            "blockers": ["RUN_NOT_UNIQUE_FOR_SEED"],
        }
    run = candidates[0]
    trace = summary_path.parent / f"2p_{matchup}_seed{args.seed}.jsonl.gz"
    blockers = []
    if not trace.exists():
        blockers.append("TRACE_MISSING")
        rows = []
        sha = None
        root = None
        errors = []
    else:
        sha = hashlib.sha256(trace.read_bytes()).hexdigest()
        rows = rows_from_gzip(trace)
        root, errors = recompute_episode(rows)
        if sha != run.get("trace_sha256"):
            blockers.append("TRACE_SHA256_MISMATCH")
        if errors:
            blockers.append("TRACE_LEAF_MISMATCH")
        if root != run.get("episode_mmr_root"):
            blockers.append("EPISODE_MMR_MISMATCH")

    scores = run.get("scores", {})
    first = float(scores.get("first_0", 0.0))
    second = float(scores.get("second_0", 0.0))
    relative = first - second
    recorded_relative = run.get("relative_payoff_seat0_minus_seat1")
    if recorded_relative is None or float(recorded_relative) != relative:
        blockers.append("RELATIVE_PAYOFF_MISMATCH")

    if blockers:
        winner_seat = "NOT_ESTABLISHED"
        winner_arm = None
    elif relative > 0:
        winner_seat = "first_0"
        winner_arm = run.get("seats", {}).get("first_0")
    elif relative < 0:
        winner_seat = "second_0"
        winner_arm = run.get("seats", {}).get("second_0")
    else:
        winner_seat = "TIE"
        winner_arm = "TIE"

    return {
        "schema": "DETERMINISTIC_GAME_OUTCOME_V1",
        "outcome_class": "TWO_PLAYER_MATCH_WINNER",
        "winner_predicate": "HIGHER_FINAL_CUMULATIVE_ENVIRONMENT_SCORE",
        "matchup": matchup,
        "seed": args.seed,
        "scores": scores,
        "relative_payoff_recomputed": relative,
        "relative_payoff_recorded": recorded_relative,
        "trace_sha256_observed": sha,
        "trace_sha256_expected": run.get("trace_sha256"),
        "trace_rows": len(rows),
        "leaf_errors": errors,
        "episode_mmr_recomputed": root,
        "episode_mmr_recorded": run.get("episode_mmr_root"),
        "winner_seat": winner_seat,
        "winner_arm": winner_arm,
        "blockers": blockers,
        "literal_game_completion_claim": "NO",
        "claim_ceiling": "FROZEN_TWO_PLAYER_MATCH_SCORE_OUTCOME_ONLY",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)

    p1 = sub.add_parser("1p")
    p1.add_argument("--results", default=str(ROOT / "results.json"))
    p1.add_argument("--left-run", type=int, required=True)
    p1.add_argument("--right-run", type=int, required=True)

    p2 = sub.add_parser("2p")
    p2.add_argument("--summary", required=True)
    p2.add_argument("--seed", type=int, required=True)

    args = ap.parse_args()
    out = compare_1p(args) if args.mode == "1p" else compare_2p(args)
    print(json.dumps(out, indent=2, sort_keys=True))
    blockers = out.get("blockers", [])
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
