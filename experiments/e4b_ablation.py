"""E4B_LATENCY_DECISION: matched context arms over the frozen E4A panel. See docs/prereg/E4B_LATENCY_DECISION.md.

This lane measures runtime and decision behaviour only. It is NOT an action-quality experiment:
the E4A quality proxy is NULL / METRIC_NOT_DISCRIMINATING (0 of 96 snapshots) and is not an endpoint here.

Everything except the decider call is computed at freeze time: arm contexts, S0 compile
timings, and the per-action unsafe-outcome table (replayed from the ALE ground truth).
The decider never sees the outcome table and no arm contains a recommended action.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import random
import time

from experiments.common import ds_dir, prereg_ref, read_jsonl, write_jsonl, write_manifest
from experiments.e4a_snapshots import IN_ID as E4A_ID, anticube
from src.actions import ACTIONS
from src.deciders import MOVE_QUESTION, ScriptedDecider
from src.openjev_client import OpenJevDecider
from src.envcfg import make_env
from src.perception import Perception
from src.s01.canon import cbytes, content_id

EXP, IN_ID, OUT_ID = "E4B_LATENCY_DECISION", "S01_E4B_LATENCY_ARM_PANEL_V1", "S01_E4B_LATENCY_OPENJEV_RESULTS_V1"
E4A_ROWS_SHA256 = "cb08c3611d1b9f909031cb278a4c9da22d891d1d7b51374e6261273502f2fc78"
HIST = 3                       # prior decisions in A1 history
H, TEMP = 4, 1.0               # path horizon (decisions) and softmin temperature
REPEAT, HORIZON = 3, 12        # unsafe proxy: chosen action x3 then NOOP, lives lost within 12 steps
ARMS = ["A0_RAW", "A1_VITACONTEXT", "A2_ANTICUBE", "A3_DELTAGSTAR", "A4_PATH_DISTRIBUTION", "A5_VITA01_FULL",
        "NULL_METADATA", "SHUFFLED_HISTORY", "SIZE_MATCHED_SHAM", "UNRELATED_HISTORY"]
NOT_TESTED_ARMS = {"A3_DELTAGSTAR": "governed private ΔG* implementation not available in this repository: NOT_COMPUTED"}
ORDER_SEED = 20260927
EXTRA_ATOMS = ["evidence/openjev/UPSTREAM_IDENTITY.json", "evidence/openjev/RUNTIME_MANIFEST.json"]
CODE = ["experiments/e4b_ablation.py", "experiments/e4a_snapshots.py", "src/deciders.py", "src/openjev_client.py", "src/perception.py", "src/envcfg.py"]
SHIP_Y, SHIP_HALF, STEP_PX = 190, 4, 2.0   # ship row, half-width, ship px per frame (x4 frames per decision)


def replay(seed: int, step: int):
    """Deterministic replay of the scripted policy; returns states at step-HIST..step."""
    env, per, dec = make_env(), Perception(), ScriptedDecider()
    obs, info = env.reset(seed=seed)
    score, prev, states = 0.0, "NOOP", []
    for t in range(step + 1):
        s = per.observe(obs, lives=int(info["lives"]), score=score, step=t, prev_action=prev)
        if t >= step - HIST:
            states.append(s)
        if t == step:
            return env, states, info
        a = dec.decide(s, prev).action
        obs, r, *_ = env.step(ACTIONS.index(a))
        score += float(r)
        prev = a


def outcome_table(seed: int, step: int) -> dict:
    out = {}
    for a in ACTIONS:
        env, _, info = replay(seed, step)
        lives0, lost = int(info["lives"]), False
        for k in range(HORIZON):
            _, _, term, trunc, info = env.step(ACTIONS.index(a) if k < REPEAT else 0)
            if int(info["lives"]) < lives0 or term:
                lost = True
                break
        env.close()
        out[a] = lost
    return out


def history_summary(states: list[dict]) -> list[dict]:
    return [{"steps_ago": len(states) - 1 - i, "ship_x": (s["ship"] or {}).get("x"),
             "bombs": [[b["x"], b["y_bottom"]] for b in s["bombs"]], "action": s["previous_action"]}
            for i, s in enumerate(states[:-1])]


def path_distribution(state: dict) -> dict:
    """Public candidate-path distribution (not ΔG*): sequences of LEFT/STAY/RIGHT over H decisions;
    cost = number of decisions at which a bomb, extrapolated with its observed dy, overlaps the ship.
    P(path) ∝ exp(-cost/TEMP); reported as mass per first move and the min-cost per first move."""
    ship = state["ship"]
    if ship is None:
        return {"state": "UNKNOWN_NO_SHIP"}
    moves = {"LEFT": -1, "STAY": 0, "RIGHT": 1}
    bombs = [(b["x"], b["y_bottom"], b["dy"] if b["dy"] else 8) for b in state["bombs"]]
    paths = []

    def rec(seq, x):
        if len(seq) == H:
            cost = 0
            xx = ship["x"]
            for k, m in enumerate(seq, 1):
                xx = min(max(xx + moves[m] * STEP_PX * 4, 20), 140)
                cost += any(abs(bx - xx) <= SHIP_HALF + 1 and by + dy * k >= SHIP_Y - 6 and by + dy * (k - 1) <= SHIP_Y + 4
                            for bx, by, dy in bombs)
            paths.append((seq, cost))
            return
        for m in moves:
            rec(seq + [m], x)
    rec([], ship["x"])
    w = [math.exp(-c / TEMP) for _, c in paths]
    Z = sum(w)
    first = {m: round(sum(wi for (s, _), wi in zip(paths, w) if s[0] == m) / Z, 4) for m in moves}
    mincost = {m: min(c for s, c in paths if s[0] == m) for m in moves}
    return {"horizon": H, "n_paths": len(paths), "mass_by_first_move": first, "min_cost_by_first_move": mincost,
            "normalization": "softmin exp(-cost/T), T=1", "label": "public path distribution; not ΔG*"}


def build_input() -> dict:
    src = ds_dir(E4A_ID) / "rows.jsonl"
    if hashlib.sha256(src.read_bytes()).hexdigest() != E4A_ROWS_SHA256:
        raise SystemExit("E4A frozen rows changed")
    e4a = list(read_jsonl(src))
    rng = random.Random(f"{EXP}|derange")
    idx = list(range(len(e4a)))
    while True:
        sh = idx[:]
        rng.shuffle(sh)
        if all(a != b for a, b in zip(idx, sh)):   # derangement across the whole panel
            break
    rows, timings = [], []
    hist = {}
    for r in e4a:
        _, states, _ = replay(r["seed"], r["step"])
        hist[r["snapshot"]] = states
    for r in e4a:
        cur = r["arms"]["RAW"]["state"]
        states = hist[r["snapshot"]]
        t0 = time.perf_counter(); h = history_summary(states); t_h = time.perf_counter() - t0
        t0 = time.perf_counter(); ac = anticube(cur); t_a = time.perf_counter() - t0
        t0 = time.perf_counter(); pd = path_distribution(cur); t_p = time.perf_counter() - t0
        other = e4a[sh[r["snapshot"]]]
        oh = history_summary(hist[other["snapshot"]])
        ostate = other["arms"]["RAW"]["state"]
        ac_dist = {k: v for k, v in ac.items()}
        full = {"state": cur, "history": h, "anticube": ac_dist, "path_distribution": pd}
        srng2 = random.Random(f"{EXP}|shufhist|{r['snapshot']}")
        own = h[:]
        while len(own) > 1:
            srng2.shuffle(own)
            if own != h:
                break
        sham_len = max(1, len(cbytes(full)) - len(cbytes({"state": cur})) - 12)
        srng = random.Random(f"{EXP}|sham|{r['snapshot']}")
        contexts = {
            "A0_RAW": {"state": cur},
            "A1_VITACONTEXT": {"state": cur, "history": h},
            "A2_ANTICUBE": {"state": cur, "history": h, "anticube": ac_dist},
            "A4_PATH_DISTRIBUTION": {"state": cur, "history": h, "anticube": ac_dist, "path_distribution": pd},
            "A5_VITA01_FULL": full,
            "NULL_METADATA": {"state": cur, "history": None, "anticube": None, "path_distribution": None},
            "SHUFFLED_HISTORY": {**full, "history": [dict(x, steps_ago=h[i]["steps_ago"]) for i, x in enumerate(own)]},
            "SIZE_MATCHED_SHAM": {"state": cur, "noninformative": "".join(srng.choice("abcdef0123456789") for _ in range(sham_len))},
            "UNRELATED_HISTORY": {**full, "history": oh},
        }
        rows.append({"snapshot": r["snapshot"], "stratum": r["stratum"], "seed": r["seed"], "step": r["step"],
                     "source_atom_id": r["source_atom_id"], "contexts": contexts,
                     "context_ids": {a: content_id(c) for a, c in contexts.items()},
                     "permuted_from": other["snapshot"]})
        timings.append({"snapshot": r["snapshot"], "s0_ms": {"history": t_h * 1000, "anticube": t_a * 1000, "paths": t_p * 1000}})
    d = ds_dir(IN_ID)
    write_jsonl(d / "rows.jsonl", rows)
    write_jsonl(d / "s0_timings.jsonl", timings)
    order = [(s, a) for s in range(len(rows)) for a in ARMS if a not in NOT_TESTED_ARMS]
    random.Random(ORDER_SEED).shuffle(order)
    write_jsonl(d / "call_order.jsonl", [{"i": i, "snapshot": s, "arm": a} for i, (s, a) in enumerate(order)])
    return write_manifest(d, dataset_id=IN_ID, schema="rows: {snapshot, contexts{arm: context}, context_ids}; call_order; s0_timings (machine-specific)",
                          kind="evaluation", source=f"{E4A_ID} rows sha256 {E4A_ROWS_SHA256}", generation_code=CODE,
                          config={"arms": ARMS, "not_tested_arms": NOT_TESTED_ARMS, "history": HIST, "path_horizon": H,
                                  "path_temperature": TEMP,
                                  "quality_endpoint": "NULL / METRIC_NOT_DISCRIMINATING / NOT_A_PRIMARY_ENDPOINT (E4A proxy: 0/96 discriminating)",
                                  "order_seed": ORDER_SEED, "question": MOVE_QUESTION, "legal_actions": list(ACTIONS)},
                          seeds={"order": ORDER_SEED, "derangement": f"{EXP}|derange", "sham": f"{EXP}|sham|<snapshot>"},
                          claim_ceiling="frozen inputs; no decider has consumed this panel")


def run() -> dict:
    from scipy.stats import wilcoxon

    manifest = json.loads((ds_dir(IN_ID).parent.parent.parent / "evidence/openjev/RUNTIME_MANIFEST.json").read_text())
    if manifest.get("OPENJEV_LOADED") != "YES":
        raise SystemExit("OpenJev runtime not verified (OPENJEV_LOADED != YES)")
    base = manifest["endpoint"].rsplit("/v1/systemone", 1)[0]
    dec = OpenJevDecider(base, os.environ.get("OPENJEV_MODEL", "openjev"), max_retries=2, timeout_s=120)
    rows = {r["snapshot"]: r for r in read_jsonl(ds_dir(IN_ID) / "rows.jsonl")}
    tim = {t["snapshot"]: t["s0_ms"] for t in read_jsonl(ds_dir(IN_ID) / "s0_timings.jsonl")}
    out, served = [], set()
    for c in read_jsonl(ds_dir(IN_ID) / "call_order.jsonl"):
        r, arm = rows[c["snapshot"]], c["arm"]
        t0 = time.perf_counter()
        body = dec.request_body(r["contexts"][arm])
        ser_ms = (time.perf_counter() - t0) * 1000
        t0 = time.perf_counter()
        d = dec.decide_body(body, "NOOP")
        dec_ms = (time.perf_counter() - t0) * 1000
        s0 = tim[c["snapshot"]]
        s0_ms = {"A0_RAW": 0.0, "C4_HASH_ONLY_SIZE_MATCHED": 0.0, "A1_VITACONTEXT": s0["history"],
                 "A2_ANTICUBE": s0["history"] + s0["anticube"]}.get(arm, s0["history"] + s0["anticube"] + s0["paths"])
        served.add(d.served_model)
        p = d.probabilities
        ent = (-sum(v * math.log2(v) for v in p.values() if v > 0) / math.log2(6)) if isinstance(p, dict) and p else None
        out.append({"i": c["i"], "snapshot": c["snapshot"], "arm": arm, "context_id": r["context_ids"][arm],
                    "request_sha256": hashlib.sha256(body).hexdigest(), "request_bytes": len(body),
                    "proposed": d.proposed_action, "executed": d.action, "fallback": d.fallback_reason,
                    "probabilities": p if p else "NOT_AVAILABLE", "confidence": d.confidence, "entropy_norm": ent,
                    "served_model": d.served_model, "input_tokens": d.input_tokens, "errors": d.errors, "retries": d.retries,
                    "ms": {"s0": round(s0_ms, 4), "serialize": round(ser_ms, 4), "decider": round(dec_ms, 2),
                           "total": round(s0_ms + ser_ms + dec_ms, 2)},
                    "labels": ["provider=openjev", "NON_TYPESAFE_JEV", "NON_COUNTED_FOR_TYPESAFE_PERFORMANCE"]})
    d_ = ds_dir(OUT_ID)
    sha, _, nrows = write_jsonl(d_ / "rows.jsonl", out)
    by = {}
    for o in out:
        by.setdefault(o["arm"], {})[o["snapshot"]] = o
    base_arm = by["A0_RAW"]
    claims, ps = [], []
    for arm in [a for a in ARMS if a != "A0_RAW" and a not in NOT_TESTED_ARMS]:
        snaps = [s for s in base_arm if s in by[arm]]
        saved = [base_arm[s]["ms"]["total"] - by[arm][s]["ms"]["total"] for s in snaps]
        p = float(wilcoxon(saved).pvalue) if any(saved) else 1.0
        ps.append(p)
        med = sorted(saved)[len(saved) // 2]
        claims.append({"id": f"T_{arm}", "arm": arm, "n": len(snaps), "median_net_time_saved_ms": round(med, 3),
                       "wilcoxon_p": p,
                       "valid_action_rate": round(sum(not by[arm][s]["fallback"] for s in snaps) / len(snaps), 4),
                       "fallback_rate": round(sum(bool(by[arm][s]["fallback"]) for s in snaps) / len(snaps), 4),
                       "action_change_rate_vs_A0": round(sum(by[arm][s]["executed"] != base_arm[s]["executed"] for s in snaps) / len(snaps), 4),
                       "action_change_note": "decision-behaviour measure only; not evidence that either action is better"})
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    m = len(ps)
    for rank, i in enumerate(order):
        adj = min(1.0, max(ps[j] * (m - k) for k, j in enumerate(order[:rank + 1])))
        c = claims[i]
        c["holm_p"] = adj
        c["state"] = ("SUPPORTED" if c["median_net_time_saved_ms"] > 0 else "NEGATIVE") if adj < 0.05 else "FAIL_TO_REJECT_H0"
    claims.append({"id": "A3_DELTAGSTAR", "state": "NOT_TESTED", "reason": NOT_TESTED_ARMS["A3_DELTAGSTAR"]})
    claims.append({"id": "QUALITY", "state": "NULL", "reason": "E4A proxy METRIC_NOT_DISCRIMINATING (0/96); NOT_A_PRIMARY_ENDPOINT"})
    mf = write_manifest(d_, dataset_id=OUT_ID, schema="rows: one decider call per (snapshot, arm) in frozen order",
                        kind="output", source=IN_ID, generation_code=CODE, config={"served_models": sorted(x for x in served if x)},
                        seeds=[], parent_evidence=[IN_ID, "evidence/openjev/RUNTIME_MANIFEST.json"],
                        claim_ceiling="OpenJev (not TypeSafe JEV); local development evidence; SIMULATED")
    states = [c["state"] for c in claims if c["id"].startswith("T_")]
    terminal = "SUPPORTED" if states and all(s == "SUPPORTED" for s in states) else (
        "PARTIAL" if any(s == "SUPPORTED" for s in states) else "FAIL_TO_REJECT_H0")
    return {"experiment_id": EXP, "question": "How does each added 0-Vita-1 context layer change OpenJev total latency and decision behaviour on matched frozen snapshots?",
            "preregistration": prereg_ref("E4B_LATENCY_DECISION.md"), "output_manifest": mf, "terminal_state": terminal,
            "claims": claims, "output_rows_sha256": sha, "rows": nrows, "not_tested": ["A3_DELTAGSTAR", "TypeSafe JEV", "LLM baseline"],
            "note": "machine-specific latency inside rows; replay comparison not applicable (no reference digest)"}
