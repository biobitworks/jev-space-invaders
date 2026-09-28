"""E5-1P: OpenJev(A0_RAW) "OJ" vs OpenJev(A5_VITA01_FULL) "VS" on full ALE episodes.
Protocol: docs/prereg/E5_LADDER.md. The decider is identical in both arms; only the context differs.
System 0 never chooses the action; packets never carry a decision field.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import time

import numpy as np

from experiments.e4a_snapshots import anticube
from experiments.e4b_ablation import path_distribution
from src.actions import ACTIONS
from src.deciders import MOVE_QUESTION
from src.envcfg import make_env
from src.fmo import hp, mmr_root
from src.perception import Perception
from src.s01.canon import content_id
from src.s01.protocol import FORBIDDEN_KEYS

ARMS = {"OJ": "A0_RAW", "VS": "A5_VITA01_FULL"}
HIST = 3


def context(arm: str, state: dict, history: list[dict]) -> dict:
    if arm == "OJ":
        return {"state": state}
    h = [{"steps_ago": len(history) - i, "ship_x": (s["ship"] or {}).get("x"),
          "bombs": [[b["x"], b["y_bottom"]] for b in s["bombs"]], "action": s["previous_action"]}
         for i, s in enumerate(history)]
    return {"state": state, "history": h, "anticube": anticube(state), "path_distribution": path_distribution(state)}


def _keys(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k
            yield from _keys(v)
    elif isinstance(o, list):
        for v in o:
            yield from _keys(v)


def run_episode(arm: str, decider, seed: int, max_decisions: int) -> tuple[dict, list]:
    env, per = make_env(), Perception()
    obs, info = env.reset(seed=seed)
    lives0, score, prev, hist, trace = int(info["lives"]), 0.0, "NOOP", [], []
    term = trunc = capped = False
    t_start = time.perf_counter()
    for t in range(max_decisions):
        t0 = time.perf_counter()
        state = per.observe(obs, lives=int(info["lives"]), score=score, step=t, prev_action=prev)
        ctx = context(arm, state, hist[-HIST:])
        s0_ms = (time.perf_counter() - t0) * 1000
        if FORBIDDEN_KEYS & set(_keys(ctx)):
            raise SystemExit("decision field in packet")
        t0 = time.perf_counter()
        body = decider.request_body(ctx)
        ser_ms = (time.perf_counter() - t0) * 1000
        t0 = time.perf_counter()
        d = decider.decide_body(body, prev)
        dec_ms = (time.perf_counter() - t0) * 1000
        obs, r, term, trunc, info = env.step(ACTIONS.index(d.action))
        score += float(r)
        rec = {"t": t, "arm": arm, "state_id": content_id(state), "context_id": content_id(ctx),
               "request_sha256": hashlib.sha256(body).hexdigest(), "action": d.action, "proposed": d.proposed_action,
               "p": d.probabilities, "conf": d.confidence, "served_model": d.served_model, "fallback": d.fallback_reason,
               "reward": float(r), "lives": int(info["lives"]), "next_frame_sha256": hashlib.sha256(obs.tobytes()).hexdigest()}
        rec["leaf"] = hp("EPISODE_LEAF_V1", t, content_id(rec)).hex()
        rec["ms"] = {"s0": round(s0_ms, 3), "serialize": round(ser_ms, 3), "decider": round(dec_ms, 2)}
        trace.append(rec)
        hist.append(state)
        prev = d.action
        if term or trunc:
            break
    else:
        capped = True
    env.close()
    root, _ = mmr_root([bytes.fromhex(x["leaf"]) for x in trace])
    dec = np.array([x["ms"]["decider"] for x in trace])
    tot = np.array([x["ms"]["s0"] + x["ms"]["serialize"] + x["ms"]["decider"] for x in trace])
    run = {"arm": arm, "context_arm": ARMS[arm], "seed": seed, "score": score, "decisions": len(trace),
           "frames": int(info["episode_frame_number"]), "lives_lost": lives0 - int(info["lives"]),
           "terminated": bool(term), "truncated": bool(trunc or capped), "max_decisions": max_decisions,
           "fallback_rate": round(sum(bool(x["fallback"]) for x in trace) / len(trace), 4),
           "latency_ms_p50": round(float(np.percentile(dec, 50)), 2), "latency_ms_p95": round(float(np.percentile(dec, 95)), 2),
           "total_ms_p50": round(float(np.percentile(tot, 50)), 2), "wall_clock_s": round(time.perf_counter() - t_start, 1),
           "served_model": ",".join(sorted({x["served_model"] for x in trace if x["served_model"]})) or None,
           "provider": "openjev", "labels": ["NON_TYPESAFE_JEV", "NON_COUNTED_FOR_TYPESAFE_PERFORMANCE"],
           "episode_mmr_root": root, "episode_mmr_size": len(trace)}
    return run, trace


def write_trace(path, trace) -> str:
    raw = "".join(json.dumps(x, separators=(",", ":")) + "\n" for x in trace).encode()
    path.write_bytes(gzip.compress(raw, mtime=0))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def latency_probe(decider, n: int = 20) -> dict:
    ms = []
    for i in range(n):
        body = decider.request_body({"state": {"label": "SETUP_SMOKE", "note": "NON_EXPERIMENTAL NOT_E4A NOT_COUNTED", "i": i}})
        t0 = time.perf_counter()
        decider.decide_body(body, "NOOP")
        ms.append((time.perf_counter() - t0) * 1000)
    a = np.array(ms)
    return {"n": n, "p50_ms": round(float(np.percentile(a, 50)), 1), "p95_ms": round(float(np.percentile(a, 95)), 1),
            "label": "SETUP_SMOKE NON_EXPERIMENTAL", "question": MOVE_QUESTION["type"]}
