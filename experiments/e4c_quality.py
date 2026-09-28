"""E4C_QUALITY: successor snapshot panel whose quality endpoint can discriminate actions.
Construction protocol: docs/prereg/E4C_QUALITY_CONSTRUCTION.md. E4A is not modified.

Every parameter below is frozen by the protocol breakpoint BEFORE the panel is built, and the
panel is built BEFORE any model sees it. Ground truth comes from ALE rollouts only.
"""
from __future__ import annotations

import hashlib
import random

from experiments.common import ds_dir, write_jsonl, write_manifest
from src.actions import ACTIONS
from src.deciders import ScriptedDecider
from src.envcfg import ENV_CONFIG, make_env
from src.perception import Perception

EXP, IN_ID = "E4C_QUALITY", "S01_E4C_QUALITY_PANEL_V1"
SEEDS = list(range(6, 16))      # disjoint from E4A seeds 1-5: no duplicate source states by construction
EVERY = 5                       # candidate every 5th decision with the ship visible
PRESCREEN_NOOP = 12             # exclude if a life is lost within 12 NOOP decisions (48 frames): state already committed
HOLD = 4                        # candidate action held for 4 decisions (16 frames)
EVAL = 24                       # unsafe = life lost or game over within 24 decisions from the snapshot
ROLLOUT = "NOOP"                # deterministic policy after the hold window
PER_STRATUM_CAP, MIN_DISCRIMINATING = 48, 24
CODE = ["experiments/e4c_quality.py", "src/envcfg.py", "src/perception.py", "src/deciders.py"]


def _rollout(env, ale, snap, first: str | None, steps: int, hold: int) -> tuple[bool, int | None]:
    ale.restoreState(snap)
    lives0 = ale.lives()
    for k in range(steps):
        a = first if (first is not None and k < hold) else ROLLOUT
        _, _, term, trunc, info = env.step(ACTIONS.index(a))
        if int(info["lives"]) < lives0 or term:
            return True, k + 1
    return False, None


def build_input() -> dict:
    cands, lag = [], []
    for seed in SEEDS:
        env, per, dec = make_env(), Perception(), ScriptedDecider()
        ale = env.unwrapped.ale
        obs, info = env.reset(seed=seed)
        score, prev, t = 0.0, "NOOP", 0
        while True:
            state = per.observe(obs, lives=int(info["lives"]), score=score, step=t, prev_action=prev)
            if t % EVERY == 0 and state["ship"] is not None:
                snap = ale.cloneState(include_rng=True)
                committed, when = _rollout(env, ale, snap, None, PRESCREEN_NOOP, 0)
                if committed:
                    lag.append(when)
                else:
                    outc = {a: _rollout(env, ale, snap, a, EVAL, HOLD)[0] for a in ACTIONS}
                    cands.append({"seed": seed, "step": t, "frame_sha256": hashlib.sha256(obs.tobytes()).hexdigest(),
                                  "stratum": "bombs" if state["bombs"] else "no_bombs", "state": state,
                                  "outcome_unsafe": outc, "n_unsafe": sum(outc.values())})
                ale.restoreState(snap)
            a = dec.decide(state, prev).action
            obs, r, term, trunc, info = env.step(ACTIONS.index(a))
            score += float(r)
            prev, t = a, t + 1
            if term or trunc:
                break
        env.close()
    seen, uniq = set(), []
    for c in cands:
        if c["frame_sha256"] not in seen:
            seen.add(c["frame_sha256"])
            uniq.append(c)
    disc = [c for c in uniq if 0 < c["n_unsafe"] < len(ACTIONS)]
    panel = []
    for st in ("bombs", "no_bombs"):
        pool = [c for c in disc if c["stratum"] == st]
        pick = random.Random(f"{EXP}|{st}").sample(pool, min(PER_STRATUM_CAP, len(pool)))
        panel += sorted(pick, key=lambda c: (c["seed"], c["step"]))
    for i, c in enumerate(panel):
        c["snapshot"] = i
    gate = "PASS" if len(panel) >= MIN_DISCRIMINATING else "BLOCKED_OR_UNDERPOWERED"
    d = ds_dir(IN_ID)
    write_jsonl(d / "rows.jsonl", panel)
    write_jsonl(d / "construction_summary.jsonl", [{
        "candidates_after_prescreen": len(cands), "unique": len(uniq), "excluded_committed": len(lag),
        "committed_lag_distribution": {str(k): lag.count(k) for k in sorted(set(lag))},
        "discriminating": len(disc), "panel": len(panel), "gate": gate,
        "n_unsafe_histogram": {str(k): sum(1 for c in uniq if c["n_unsafe"] == k) for k in range(7)}}])
    m = write_manifest(d, dataset_id=IN_ID, schema="rows: {snapshot, seed, step, frame_sha256, stratum, state, outcome_unsafe, n_unsafe}",
                       kind="evaluation", source="ALE/SpaceInvaders-v5 scripted-policy states, seeds 6-15",
                       generation_code=CODE,
                       config={"env": ENV_CONFIG, "every": EVERY, "prescreen_noop": PRESCREEN_NOOP, "hold": HOLD, "eval": EVAL,
                               "rollout": ROLLOUT, "cap": PER_STRATUM_CAP, "min_discriminating": MIN_DISCRIMINATING, "gate": gate},
                       seeds={"episodes": SEEDS, "sampling": f"{EXP}|<stratum>"},
                       claim_ceiling="ground-truth panel construction only; no model has seen it")
    m["gate"] = gate
    return m
