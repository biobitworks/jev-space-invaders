"""E4C_EXHAUSTIVE_REACHABLE_ACTION_GRAPH (Atari, six-action ALE schema). Protocol:
docs/prereg/E4C_EXHAUSTIVE_REACHABLE_ACTION_GRAPH.md. Supersedes the never-frozen hold x4 -> NOOP draft.

From each root: restore the exact emulator state, expand all 6 actions per decision to horizon H,
key every node by SHA-256 of ale.cloneState(include_rng=True).serialize() plus depth, merge exact
transpositions, stop at life loss / game over. No interval compression is applied (none is proven).
"""
from __future__ import annotations

import hashlib
import random

from experiments.common import ds_dir, write_jsonl, write_manifest
from src.actions import ACTIONS
from src.deciders import ScriptedDecider
from src.envcfg import ENV_CONFIG, make_env
from src.perception import Perception

EXP, IN_ID = "E4C_EXHAUSTIVE_REACHABLE_ACTION_GRAPH", "S01_E4C_GRAPH_PANEL_V1"
SEEDS, EVERY, H = list(range(6, 16)), 10, 4
ROOT_CAP, MIN_DISCRIMINATING, PER_STRATUM_CAP = 240, 24, 48
CODE = ["experiments/e4c_graph.py", "src/envcfg.py", "src/perception.py", "src/deciders.py"]


def expand(env, ale, root_state, lives0: int) -> dict:
    """Returns per first action: survivable (any surviving leaf), safe_leaf_paths, node counts."""
    per = {}
    for a0 in ACTIONS:
        frontier = {}                                   # key -> (state, path multiplicity)
        ale.restoreState(root_state)
        _, _, term, _, info = env.step(ACTIONS.index(a0))
        if int(info["lives"]) < lives0 or term:
            per[a0] = {"survivable": False, "safe_paths": 0, "nodes": 1}
            continue
        s = ale.cloneState(include_rng=True)
        frontier[hashlib.sha256(s.serialize()).hexdigest()] = (s, 1)
        nodes, merges = 1, 0
        for _ in range(H - 1):
            nxt = {}
            for st, mult in frontier.values():
                for a in ACTIONS:
                    ale.restoreState(st)
                    _, _, term, _, info = env.step(ACTIONS.index(a))
                    if int(info["lives"]) < lives0 or term:
                        continue
                    ns = ale.cloneState(include_rng=True)
                    k = hashlib.sha256(ns.serialize()).hexdigest()
                    if k in nxt:
                        nxt[k] = (nxt[k][0], nxt[k][1] + mult)
                        merges += 1
                    else:
                        nxt[k] = (ns, mult)
                        nodes += 1
            frontier = nxt
        safe = sum(m for _, m in frontier.values())
        per[a0] = {"survivable": safe > 0, "safe_paths": safe, "safe_fraction": safe / 6 ** (H - 1),
                   "nodes": nodes, "transposition_merges": merges}
    return per


def build_input() -> dict:
    cands = []
    for seed in SEEDS:
        env, perc, dec = make_env(), Perception(), ScriptedDecider()
        obs, info = env.reset(seed=seed)
        score, prev, t = 0.0, "NOOP", 0
        while True:
            state = perc.observe(obs, lives=int(info["lives"]), score=score, step=t, prev_action=prev)
            if t % EVERY == 0 and state["ship"] is not None:
                cands.append((seed, t))
            a = dec.decide(state, prev).action
            obs, r, term, trunc, info = env.step(ACTIONS.index(a))
            score += float(r)
            prev, t = a, t + 1
            if term or trunc:
                break
        env.close()
    roots = sorted(random.Random(f"{EXP}|roots").sample(cands, min(ROOT_CAP, len(cands))))
    rows = []
    for seed, step in roots:
        env, perc, dec = make_env(), Perception(), ScriptedDecider()
        ale = env.unwrapped.ale
        obs, info = env.reset(seed=seed)
        score, prev = 0.0, "NOOP"
        for t in range(step + 1):
            state = perc.observe(obs, lives=int(info["lives"]), score=score, step=t, prev_action=prev)
            if t == step:
                break
            a = dec.decide(state, prev).action
            obs, r, *_ = env.step(ACTIONS.index(a))
            score += float(r)
            prev = a
        root = ale.cloneState(include_rng=True)
        per = expand(env, ale, root, int(info["lives"]))
        env.close()
        fr = sorted((v.get("safe_fraction", 0.0) for v in per.values()), reverse=True)
        best = fr[0]
        rows.append({"seed": seed, "step": step, "root_state_sha256": hashlib.sha256(root.serialize()).hexdigest(),
                     "frame_sha256": hashlib.sha256(obs.tobytes()).hexdigest(), "stratum": "bombs" if state["bombs"] else "no_bombs",
                     "state": state, "per_first_action": per,
                     "optimal_action_set": sorted(a for a, v in per.items() if v.get("safe_fraction", 0.0) == best and v["survivable"]),
                     "decision_margin": fr[0] - fr[1],
                     "regret": {a: best - v.get("safe_fraction", 0.0) for a, v in per.items()},
                     "discriminating": 0 < sum(v["survivable"] for v in per.values()) < len(ACTIONS)})
    disc = [r for r in rows if r["discriminating"]]
    panel = []
    for st in ("bombs", "no_bombs"):
        pool = [r for r in disc if r["stratum"] == st]
        panel += sorted(random.Random(f"{EXP}|{st}").sample(pool, min(PER_STRATUM_CAP, len(pool))), key=lambda r: (r["seed"], r["step"]))
    for i, r in enumerate(panel):
        r["snapshot"] = i
    gate = "PASS" if len(panel) >= MIN_DISCRIMINATING else "BLOCKED_OR_UNDERPOWERED"
    d = ds_dir(IN_ID)
    write_jsonl(d / "rows.jsonl", panel)
    write_jsonl(d / "all_roots.jsonl", rows)
    m = write_manifest(d, dataset_id=IN_ID, schema="rows: panel roots with exhaustive per-first-action outcomes; all_roots: every expanded root",
                       kind="evaluation", source="ALE/SpaceInvaders-v5 scripted-policy states, seeds 6-15", generation_code=CODE,
                       config={"env": ENV_CONFIG, "H": H, "every": EVERY, "root_cap": ROOT_CAP, "min_discriminating": MIN_DISCRIMINATING,
                               "per_stratum_cap": PER_STRATUM_CAP, "actions": list(ACTIONS), "gate": gate,
                               "node_key": "sha256(ALEState.serialize()) per depth (includes RAM, RNG, frame counters)",
                               "compression": "none"},
                       seeds={"episodes": SEEDS, "roots": f"{EXP}|roots", "sampling": f"{EXP}|<stratum>"},
                       claim_ceiling="exhaustive ground truth to horizon H only; no model has seen these states")
    m["gate"] = gate
    return m
