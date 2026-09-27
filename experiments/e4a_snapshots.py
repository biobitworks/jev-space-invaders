"""E4A Space Invaders frozen snapshot panel (input freeze only; no decider calls).
See docs/prereg/E4A_SPACE_INVADERS_SNAPSHOTS.md."""
from __future__ import annotations

import hashlib
import random

from experiments.common import ds_dir, write_jsonl, write_manifest
from src.actions import ACTIONS
from src.deciders import ScriptedDecider
from src.envcfg import ENV_CONFIG, make_env, runtime_versions
from src.perception import VERSION as PERCEPTION_VERSION, Perception
from src.s01.canon import cbytes, content_id

EXP, IN_ID = "E4A_SPACE_INVADERS_SNAPSHOTS", "S01_SPACE_INVADERS_SNAPSHOT_EVAL_V1"
SEEDS, EVERY, PER_STRATUM = [1, 2, 3, 4, 5], 10, 48
CODE = ["experiments/e4a_snapshots.py", "src/perception.py", "src/envcfg.py", "src/deciders.py", "src/s01/canon.py"]
ANTICUBE_RULES = {
    "ship": "SELF; UNSAFE if a bomb has |x - ship.x| <= 8 and y_bottom >= 150, else SAFE; UNKNOWN/UNKNOWN if not visible",
    "own_shots": "SELF/SAFE", "bombs": "NONSELF/UNSAFE", "aliens": "NONSELF/UNSAFE",
    "shields": "NONSELF/SAFE", "unknown_shots": "UNKNOWN/UNKNOWN",
}


def anticube(state: dict) -> dict:
    ship = state["ship"]
    if ship is None:
        s = {"identity": "UNKNOWN", "safety": "UNKNOWN"}
    else:
        near = any(abs(b["x"] - ship["x"]) <= 8 and b["y_bottom"] >= 150 for b in state["bombs"])
        s = {"identity": "SELF", "safety": "UNSAFE" if near else "SAFE"}
    return {"ship": s,
            "own_shots": [{"identity": "SELF", "safety": "SAFE"} for _ in state["own_shots"]],
            "bombs": [{"identity": "NONSELF", "safety": "UNSAFE"} for _ in state["bombs"]],
            "aliens": {"identity": "NONSELF", "safety": "UNSAFE"} if state["aliens"]["present"] else None,
            "shields": [{"identity": "NONSELF", "safety": "SAFE"} for _ in state["shields"]],
            "unknown_shots": [{"identity": "UNKNOWN", "safety": "UNKNOWN"} for _ in state["unknown_shots"]]}


def play_to(seed: int, step: int):
    """Deterministic replay of the scripted policy to `step`; returns (frame, ram, state)."""
    env, per, dec = make_env(), Perception(), ScriptedDecider()
    obs, info = env.reset(seed=seed)
    score, prev = 0.0, "NOOP"
    for t in range(step + 1):
        state = per.observe(obs, lives=int(info["lives"]), score=score, step=t, prev_action=prev)
        if t == step:
            ram = env.unwrapped.ale.getRAM().tobytes()
            env.close()
            return obs, ram, state
        a = dec.decide(state, prev).action
        obs, r, term, trunc, info = env.step(ACTIONS.index(a))
        score += float(r)
        prev = a
        if term or trunc:
            env.close()
            return None


def candidates():
    out = []
    for seed in SEEDS:
        env, per, dec = make_env(), Perception(), ScriptedDecider()
        obs, info = env.reset(seed=seed)
        score, prev, t = 0.0, "NOOP", 0
        while True:
            state = per.observe(obs, lives=int(info["lives"]), score=score, step=t, prev_action=prev)
            if t % EVERY == 0 and state["ship"] is not None:
                out.append({"seed": seed, "step": t, "frame_sha256": hashlib.sha256(obs.tobytes()).hexdigest(),
                            "ram_sha256": hashlib.sha256(env.unwrapped.ale.getRAM().tobytes()).hexdigest(),
                            "state": state})
            a = dec.decide(state, prev).action
            obs, r, term, trunc, info = env.step(ACTIONS.index(a))
            score += float(r)
            prev, t = a, t + 1
            if term or trunc:
                break
        env.close()
    return out


def build_input() -> dict:
    cands = candidates()
    strata = {"bombs": [c for c in cands if c["state"]["bombs"]], "no_bombs": [c for c in cands if not c["state"]["bombs"]]}
    picked = []
    for name, items in strata.items():
        rng = random.Random(f"E4A|{name}")
        for c in sorted(rng.sample(items, min(PER_STRATUM, len(items))), key=lambda c: (c["seed"], c["step"])):
            picked.append({**c, "stratum": name})
    # replay verification: every frozen snapshot must be reproducible from (seed, step)
    for c in picked:
        frame, ram, _ = play_to(c["seed"], c["step"])
        if hashlib.sha256(frame.tobytes()).hexdigest() != c["frame_sha256"] or hashlib.sha256(ram).hexdigest() != c["ram_sha256"]:
            raise SystemExit(f"snapshot replay mismatch seed {c['seed']} step {c['step']}")
    # matched controls
    rows = []
    by_stratum = {}
    for i, c in enumerate(picked):
        by_stratum.setdefault(c["stratum"], []).append(i)
    perm = {}
    for name, idx in by_stratum.items():
        rng = random.Random(f"E4A-perm|{name}")
        while True:
            sh = idx[:]
            rng.shuffle(sh)
            if len(idx) < 2 or all(a != b for a, b in zip(idx, sh)):
                break
        perm.update(dict(zip(idx, sh)))
    for i, c in enumerate(picked):
        ac = anticube(c["state"])
        ac_perm = anticube(picked[perm[i]]["state"])
        n = len(cbytes(ac))
        rng = random.Random(f"E4A-sham|{i}")
        sham = "".join(rng.choice("abcdefghijklmnopqrstuvwxyz") for _ in range(max(1, n - 2)))
        source_atom = {"kind": "SourceAtomFCO", "domain": "space_invaders", "frame_sha256": c["frame_sha256"],
                       "ram_sha256": c["ram_sha256"], "seed": c["seed"], "step": c["step"]}
        rows.append({"snapshot": i, "stratum": c["stratum"], "seed": c["seed"], "step": c["step"],
                     "policy": "scripted-policy (src/deciders.py ScriptedDecider period=30)",
                     "frame_sha256": c["frame_sha256"], "ram_sha256": c["ram_sha256"],
                     "source_atom_id": content_id(source_atom), "legal_actions": list(ACTIONS),
                     "arms": {"RAW": {"state": c["state"]},
                              "ANTICUBE": {"state": c["state"], "anticube": ac},
                              "PERMUTED": {"state": c["state"], "anticube": ac_perm, "permuted_from": perm[i]},
                              "SIZE_MATCHED_SHAM": {"state": c["state"], "sham": sham},
                              "S0_CONTEXT": "NOT_TESTED_PRIVATE_S0", "S0_GOLDEN": "NOT_TESTED_PRIVATE_S0"}})
    d = ds_dir(IN_ID)
    write_jsonl(d / "rows.jsonl", rows)
    return write_manifest(d, dataset_id=IN_ID, schema="rows: {snapshot, stratum, seed, step, policy, frame_sha256, ram_sha256, source_atom_id, legal_actions, arms{...}}",
                          kind="evaluation", source="ALE/SpaceInvaders-v5 replay of scripted policy",
                          generation_code=CODE,
                          config={"env": ENV_CONFIG, "every": EVERY, "per_stratum": PER_STRATUM,
                                  "perception": PERCEPTION_VERSION, "anticube_rules": ANTICUBE_RULES,
                                  "runtime": runtime_versions(), "replay_verified": True, "candidates": len(cands),
                                  "stratum_sizes": {k: len(v) for k, v in strata.items()}},
                          seeds={"episodes": SEEDS, "selection": "random.Random('E4A|<stratum>')"},
                          license="derived observations only; no ROM bytes",
                          claim_ceiling="frozen inputs only; no decider has been queried")
