"""E5-2P: PettingZoo space_invaders_v2 (Parallel API). Separate ontology, question, perception, schema.
ALE and PettingZoo action bytes do NOT share semantics (TYPE_ERROR_T8).
The ROM is never acquired here: a directory holding space_invaders.bin must be supplied explicitly
(Byron's licence decision) and its hashes are recorded; without it the lane is ROM_GATE_BLOCKED.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import numpy as np

from experiments.e4a_snapshots import anticube
from experiments.e4b_ablation import path_distribution
from src.fmo import hp, mmr_root
from src.s01.canon import content_id

ONTOLOGY_PZ = ("NOOP", "FIRE", "UP", "RIGHT", "LEFT", "DOWN")
ONTOLOGY_ALE = ("NOOP", "FIRE", "RIGHT", "LEFT", "RIGHTFIRE", "LEFTFIRE")
ONTOLOGY_IDS = {"ALE": content_id({"ontology": "ALE_SPACE_INVADERS_MINIMAL", "actions": list(ONTOLOGY_ALE)}),
                "PZ": content_id({"ontology": "PETTINGZOO_SPACE_INVADERS_V2_MINIMAL", "actions": list(ONTOLOGY_PZ)})}
QUESTION_2P = {"type": "choice",
               "instructions": ("You control YOUR cannon (`own_ship`) in two-player Space Invaders; `opponent_ship` is the other "
                                "player. Choose one action. Priorities: avoid falling `bombs`, shoot aliens. "
                                "RIGHT increases x, LEFT decreases x. UP and DOWN are separate actions in this game."),
               "criteria": {"NOOP": "do nothing", "FIRE": "fire", "UP": "the UP action", "RIGHT": "move right",
                            "LEFT": "move left", "DOWN": "the DOWN action"}}
SEAT_COLOURS_DEFAULT = {"first_0": (50, 132, 50), "second_0": (162, 134, 56)}   # verify on PZ frames before freezing
SHIP_ROWS = (185, 195)


def request_body_2p(decider, context: dict) -> bytes:
    return json.dumps({"state": context, "model": decider.requested_model, "questions": {"move": QUESTION_2P}}).encode()


def rom_gate(rom_dir: str | None) -> dict:
    if not rom_dir:
        return {"state": "ROM_GATE_BLOCKED", "reason": "no ROM directory supplied; licence acceptance is Byron's decision"}
    p = Path(rom_dir) / "space_invaders.bin"
    if not p.exists():
        return {"state": "ROM_GATE_BLOCKED", "reason": f"{p} not found"}
    b = p.read_bytes()
    return {"state": "ROM_PRESENT", "path": str(p), "sha256": hashlib.sha256(b).hexdigest(),
            "md5": hashlib.md5(b).hexdigest(), "bytes": len(b)}


def ship_x(frame: np.ndarray, rgb) -> float | None:
    sub = frame[SHIP_ROWS[0]:SHIP_ROWS[1]]
    m = (sub[..., 0] == rgb[0]) & (sub[..., 1] == rgb[1]) & (sub[..., 2] == rgb[2])
    xs = np.nonzero(m.any(axis=0))[0]
    return float((xs.min() + xs.max()) / 2) if xs.size else None


def seat_state(base_state: dict, frame: np.ndarray, seat: str, colours: dict) -> dict:
    """Per-seat view: only what this seat's own observation shows."""
    other = [s for s in colours if s != seat][0]
    own, opp = ship_x(frame, colours[seat]), ship_x(frame, colours[other])
    st = {k: v for k, v in base_state.items() if k != "ship"}
    st["own_ship"] = None if own is None else {"x": own}
    st["opponent_ship"] = None if opp is None else {"x": opp}
    return st


def seat_context(arm: str, st: dict, history: list[dict]) -> dict:
    if arm == "OJ":
        return {"state": st}
    as1p = {**st, "ship": st["own_ship"]}
    return {"state": st, "history": [{"steps_ago": len(history) - i, "own_x": (h["own_ship"] or {}).get("x")}
                                     for i, h in enumerate(history)],
            "anticube": anticube(as1p), "path_distribution": path_distribution(as1p)}


def run_match(env_fn, perception_fn, deciders: dict, arms: dict, seed: int, max_decisions: int, colours=None):
    """env_fn() -> PettingZoo parallel env; deciders/arms keyed by seat. Returns (summary, 2P rows)."""
    colours = colours or SEAT_COLOURS_DEFAULT
    env = env_fn()
    obs, infos = env.reset(seed=seed)
    percs = {s: perception_fn() for s in env.agents}
    score = {s: 0.0 for s in env.agents}
    hist = {s: [] for s in env.agents}
    rows, leaves, lat = [], [], {s: [] for s in env.agents}
    for t in range(max_decisions):
        acts, meta = {}, {}
        for s in env.agents:
            base = percs[s].observe(obs[s], lives=0, score=score[s], step=t, prev_action="NOOP")
            st = seat_state(base, obs[s], s, colours)
            ctx = seat_context(arms[s], st, hist[s][-3:])
            body = request_body_2p(deciders[s], ctx)
            t0 = time.perf_counter()
            d = deciders[s].decide_body(body, "NOOP")
            lat[s].append((time.perf_counter() - t0) * 1000)
            a = d.proposed_action if d.proposed_action in ONTOLOGY_PZ else "NOOP"
            acts[s] = ONTOLOGY_PZ.index(a)
            meta[s] = {"action": a, "proposed": d.proposed_action, "p": d.probabilities, "context_id": content_id(ctx),
                       "fallback": None if d.proposed_action in ONTOLOGY_PZ else "choice_not_in_PZ_ontology"}
            hist[s].append(st)
        obs, rew, terms, truncs, infos = env.step(acts)
        for s in rew:
            score[s] += float(rew[s])
        a0, a1 = env.possible_agents
        row = {"corpus_id": "VITHIA_E5_2P_ROWS_V1", "t": t, "state_id": content_id({s: meta[s]["context_id"] for s in meta}),
               "vita_action": meta[a0]["action"], "opponent_action": meta[a1]["action"],
               "successor_state_id": content_id({"obs": {s: hashlib.sha256(obs[s].tobytes()).hexdigest() for s in obs}}),
               "vita_outcome": float(rew.get(a0, 0.0)), "opponent_outcome": float(rew.get(a1, 0.0)),
               "relative_payoff": float(rew.get(a0, 0.0)) - float(rew.get(a1, 0.0)),
               "seats": {a0: arms[a0], a1: arms[a1]}, "action_ontology_id": ONTOLOGY_IDS["PZ"], "meta": meta}
        row["leaf"] = hp("EPISODE_LEAF_V1", t, content_id(row)).hex()
        rows.append(row)
        leaves.append(bytes.fromhex(row["leaf"]))
        if not env.agents or all(terms.get(s) or truncs.get(s) for s in terms):
            break
    env.close()
    root, _ = mmr_root(leaves)
    return {"seed": seed, "seats": arms, "scores": score, "relative_payoff_seat0_minus_seat1": score.get("first_0", 0) - score.get("second_0", 0),
            "decisions": len(rows), "latency_ms_p50": {s: round(float(np.percentile(v, 50)), 2) for s, v in lat.items() if v},
            "episode_mmr_root": root, "provider": "openjev", "labels": ["NON_TYPESAFE_JEV", "SUCCESSOR_NOT_PILOT"]}, rows
