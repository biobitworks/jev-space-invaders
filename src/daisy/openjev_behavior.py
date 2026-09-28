"""OPENJEV_DAISY_BEHAVIOR_CORPUS_V1 and VITHIA_OPENJEV_COMPARISON_V1.

OpenJev (provider=openjev, NON_TYPESAFE_JEV) is a behavioral comparator, never ground truth. Behavior
rows are written to their own corpus and joined to the deterministic corpus only by exact state_id.
"""
from __future__ import annotations

import json
import random
import time

from src.daisy import deltag_candidate as dg
from src.daisy import eca_corpus as e
from src.s01.protocol import FORBIDDEN_KEYS

ARMS = ["A0_RAW", "A1_VITACONTEXT", "A2_ANTICUBE", "A4_PATH_DISTRIBUTION", "A5_VITA01_FULL",
        "NULL_METADATA", "SHUFFLED_HISTORY", "SIZE_MATCHED_SHAM", "UNRELATED_HISTORY"]
QUESTION = {"type": "choice",
            "instructions": "You steer a ship at position `x` on a ring of width `W`. Hazards (1s in `row`) fall onto the ship row each step. Choose the move for this step that keeps the ship alive.",
            "criteria": {"LEFT": "move one cell left", "STAY": "stay", "RIGHT": "move one cell right"}}


def roots(action_rows: list[dict]) -> list[dict]:
    seen, out = set(), []
    for r in action_rows:
        if r["state_id"] not in seen:
            seen.add(r["state_id"])
            out.append(r)
    return out


def behavior_rows(action_rows: list[dict], decider, split: str = "validation", seed: int = 20260928) -> list[dict]:
    rs = [r for r in roots(action_rows) if r["split"] == split]
    rng = random.Random(seed)
    order = [(i, a) for i in range(len(rs)) for a in ARMS]
    rng.shuffle(order)
    out = []
    for i, arm in order:
        r = rs[i]
        ctx = e.arm_context(r, arm, other=rs[(i + 1) % len(rs)], seed=i)
        assert not (FORBIDDEN_KEYS & set(json.dumps(ctx).split('"'))), "decision leakage"
        body = json.dumps({"state": ctx, "model": decider.requested_model, "questions": {"move": QUESTION}}).encode()
        t0 = time.perf_counter()
        d = decider.decide_body(body, "STAY")
        out.append({"corpus_id": "OPENJEV_DAISY_BEHAVIOR_CORPUS_V1", "state_id": r["state_id"], "arm": arm,
                    "provider": "openjev", "labels": ["NON_TYPESAFE_JEV", "BEHAVIORAL_EVIDENCE_NOT_GROUND_TRUTH"],
                    "served_model": d.served_model, "proposed": d.proposed_action, "action": d.action,
                    "fallback": d.fallback_reason, "probabilities": d.probabilities or "NOT_AVAILABLE",
                    "confidence": d.confidence, "model_latency_ms": round((time.perf_counter() - t0) * 1000, 2)})
    return out


def comparison_rows(action_rows: list[dict], behavior: list[dict]) -> list[dict]:
    gt = {}
    for r in action_rows:
        gt.setdefault(r["state_id"], {})[r["action"]] = r
    out = []
    for b in behavior:
        g = gt.get(b["state_id"])
        if g is None or b["action"] not in g:
            continue
        a = g[b["action"]]
        unsafe = {k: (0 if v["survivable"] else 1) for k, v in g.items()}
        out.append({"corpus_id": "VITHIA_OPENJEV_COMPARISON_V1", "state_id": b["state_id"], "arm": b["arm"],
                    "action": b["action"], "optimal_action_set": a["optimal_action_set"],
                    "optimal_set_hit": b["action"] in a["optimal_action_set"], "regret": a["regret"],
                    "survivable": a["survivable"], "fallback": b["fallback"],
                    **dg.compute(b["probabilities"], unsafe, b["action"])})
    return out
