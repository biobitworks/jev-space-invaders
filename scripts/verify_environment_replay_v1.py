#!/usr/bin/env python3
"""Deterministic, model-free environment replay of the submitted 240-frame ALE playthrough.

Regenerates every observation from ALE (seed, frozen config, committed ordered action stream).
Committed PNGs are never used as generated observations; committed occurrence/leaf records are
comparison references only. Mismatches are recorded, never tuned around.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.fmo import hp, mmr_root  # noqa: E402
from src.frame_custody_final import frame_local_atoms, frame_local_merkle_root  # noqa: E402

FINAL = ROOT / "evidence/competition/final_execution"
FRAMES = FINAL / "frames"
EXPECTED_MMR_ROOT = "e55a47a7f16064477c4f101a38a849391c2fbc9f6557c5244daf0406b36dbd74"
SOURCE_COMMIT = "4c943a92e84d0fb2cd3d01e4fdf15a10991eda71"
FROZEN_ENV = {"env_id": "ALE/SpaceInvaders-v5", "obs_type": "rgb", "frameskip": 1,
              "decision_hold_frames": 4, "repeat_action_probability": 0.25,
              "full_action_space": False, "max_num_frames_per_episode": 108000}
ACTIONS = ("NOOP", "FIRE", "RIGHT", "LEFT", "RIGHTFIRE", "LEFTFIRE")


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def pubkey_fingerprint_from_pem(pem: bytes) -> str:
    from cryptography.hazmat.primitives import serialization
    pub = serialization.load_pem_public_key(pem)
    raw = pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    return sha256_bytes(raw)


def policy_rule(decision_index: int, period: int) -> str:
    return "RIGHTFIRE" if (decision_index // period) % 2 == 0 else "LEFTFIRE"


def runtime_versions() -> dict:
    v = {"python": platform.python_version(), "platform": platform.platform()}
    for mod in ("ale_py", "gymnasium", "numpy", "PIL", "cryptography"):
        try:
            m = __import__(mod)
            v[mod] = getattr(m, "__version__", "UNKNOWN")
        except Exception as e:  # noqa: BLE001
            v[mod] = f"IMPORT_FAILED:{type(e).__name__}"
    return v


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--receipt", required=True)
    ap.add_argument("--locus", default="LOCAL", help="LOCAL or TENKI_SANDBOX (caller-asserted, recorded verbatim)")
    a = ap.parse_args()

    prereg = json.loads((FINAL / "FINAL_1P_RUN_PREREG.json").read_text())
    fco = json.loads((FINAL / "PLAYTHROUGH_FCO.json").read_text())
    construction = json.loads((FRAMES / "PLAYTHROUGH_MMR_CONSTRUCTION_RECEIPT.json").read_text())
    rows = [json.loads(l) for l in (FRAMES / "FRAME_BREAKPOINT_LEAVES.jsonl").read_text().splitlines() if l.strip()]
    seed, n_expected = int(fco["seed"]), int(fco["frame_count"])
    period = int(prereg["policy"]["period_decisions"])
    hold = int(prereg["environment"]["decision_hold_frames"])
    envcfg = prereg["environment"]

    config_frozen_ok = all(envcfg.get(k) == v for k, v in FROZEN_ENV.items())
    pub_pem = (FINAL / "FRAME_CUSTODY_PUBLIC_KEY.pem").read_bytes()
    pubkey_fp = pubkey_fingerprint_from_pem(pub_pem)
    expected_root = construction["mmr_root"]

    r = {"schema": "ENVIRONMENT_REPLAY_VERIFICATION_RECEIPT_V1", "source_commit": SOURCE_COMMIT,
         "execution_locus": a.locus, "seed": seed, "environment": envcfg["env_id"],
         "frozen_config": envcfg, "config_matches_frozen_contract": config_frozen_ok,
         "decision_hold_frames": hold, "frames_expected": n_expected, "frames_generated": 0,
         "first_mismatch_frame": None, "first_mismatch_kind": None,
         "first_mismatch_expected": None, "first_mismatch_observed": None,
         "mismatch_counts": {"RGB_HASH": 0, "SCORE": 0, "LIVES": 0, "ACTION": 0, "POLICY_RULE": 0,
                             "FRAME_ROOT": 0, "STEP_HASH": 0, "PNG_BYTES": 0, "LEAF_ROW": 0},
         "expected_mmr_root": expected_root, "contract_expected_mmr_root": EXPECTED_MMR_ROOT,
         "recomputed_mmr_root": None, "runtime_versions": runtime_versions(),
         "used_committed_pngs_as_observations": False}

    def note(frame, kind, exp, obs):
        r["mismatch_counts"][kind] += 1
        if r["first_mismatch_frame"] is None or frame < r["first_mismatch_frame"]:
            r["first_mismatch_frame"], r["first_mismatch_kind"] = frame, kind
            r["first_mismatch_expected"], r["first_mismatch_observed"] = exp, obs

    try:
        import ale_py
        import gymnasium as gym
        from PIL import Image
        gym.register_envs(ale_py)
        env = gym.make(envcfg["env_id"], obs_type=envcfg["obs_type"], frameskip=envcfg["frameskip"],
                       repeat_action_probability=envcfg["repeat_action_probability"],
                       full_action_space=envcfg["full_action_space"],
                       max_num_frames_per_episode=envcfg["max_num_frames_per_episode"])
        meanings = tuple(env.unwrapped.get_action_meanings())
        if meanings != ACTIONS:
            raise RuntimeError(f"ALE action set {meanings} != {ACTIONS}")
        obs, info = env.reset(seed=seed)
    except Exception as e:  # noqa: BLE001
        r.update({"environment_replay": "BLOCKED", "blocker": f"ENV_CONSTRUCTION_FAILED:{type(e).__name__}:{e}"})
        Path(a.receipt).parent.mkdir(parents=True, exist_ok=True)
        Path(a.receipt).write_text(json.dumps(r, indent=2, sort_keys=True) + "\n")
        print("ENVIRONMENT_REPLAY=BLOCKED")
        return 2

    score, leaves = 0.0, []
    term = trunc = False
    for i in range(n_expected):
        if i >= len(rows):
            note(i, "LEAF_ROW", "committed leaf row", "MISSING")
            break
        row = rows[i]
        occ = json.loads((FRAMES / f"frame_{i:04d}.occurrence.json").read_text())
        action, dec = row["action"], i // hold
        raw_sha = sha256_bytes(obs.tobytes())
        lives = int(info.get("lives", 0))
        buf = io.BytesIO()
        Image.fromarray(obs).save(buf, format="PNG")
        png_sha = sha256_bytes(buf.getvalue())
        atoms = frame_local_atoms(i, dec, raw_sha, action, score, lives, row["model_id"],
                                  envcfg["env_id"], pubkey_fp)
        froot = frame_local_merkle_root(atoms)
        step_hash = hp("FRAME_OCCURRENCE_V1", i, raw_sha, png_sha).hex()

        if raw_sha != occ["content_sha256"]:
            note(i, "RGB_HASH", occ["content_sha256"], raw_sha)
        if score != occ["score"] or score != row["score"]:
            note(i, "SCORE", occ["score"], score)
        if lives != occ["lives"] or lives != row["lives"]:
            note(i, "LIVES", occ["lives"], lives)
        if action != occ["action"] or dec != row["decision_index"] or dec != occ["decision_index"]:
            note(i, "ACTION", f"{occ['action']}@d{occ['decision_index']}", f"{action}@d{dec}")
        if action != policy_rule(dec, period):
            note(i, "POLICY_RULE", policy_rule(dec, period), action)
        if froot != occ["frame_root"] or froot != row["frame_root"]:
            note(i, "FRAME_ROOT", occ["frame_root"], froot)
        if png_sha != occ["png_artifact_sha256"]:
            note(i, "PNG_BYTES", occ["png_artifact_sha256"], png_sha)
        if step_hash != occ["occurrence_id"] or step_hash != row["occurrence_id"]:
            note(i, "STEP_HASH", occ["occurrence_id"], step_hash)
        leaves.append(bytes.fromhex(froot))
        r["frames_generated"] += 1

        obs, reward, term, trunc, info = env.step(ACTIONS.index(action))
        score += float(reward)
        if (term or trunc) and i + 1 < n_expected:
            note(i + 1, "LEAF_ROW", "episode continues", "EPISODE_ENDED_EARLY")
            break
    env.close()

    recomputed, peaks = mmr_root(leaves)
    r["recomputed_mmr_root"], r["recomputed_mmr_size"] = recomputed, len(leaves)
    mc = r["mismatch_counts"]
    eq = lambda *ks: "PASS" if all(mc[k] == 0 for k in ks) and r["frames_generated"] == n_expected else "FAIL"
    r["rgb_hash_equality"] = eq("RGB_HASH")
    r["score_equality"] = eq("SCORE")
    r["lives_equality"] = eq("LIVES")
    r["action_stream_equality"] = eq("ACTION", "POLICY_RULE")
    r["frame_root_equality"] = eq("FRAME_ROOT")
    r["step_hash_equality"] = eq("STEP_HASH")
    r["png_bytes_equality_informational"] = eq("PNG_BYTES")
    r["final_mmr_equality"] = "PASS" if (recomputed == expected_root == EXPECTED_MMR_ROOT
                                         and len(leaves) == n_expected) else "FAIL"
    r["replay_from_start"] = "PASS" if (r["frames_generated"] == n_expected and r["first_mismatch_frame"] is None
                                        and config_frozen_ok) else "FAIL"
    required = ("rgb_hash_equality", "score_equality", "lives_equality", "action_stream_equality",
                "frame_root_equality", "step_hash_equality", "final_mmr_equality", "replay_from_start")
    r["environment_replay"] = "PASS" if (all(r[k] == "PASS" for k in required)
                                         and r["first_mismatch_frame"] is None) else "FAIL"
    r["created_utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    Path(a.receipt).parent.mkdir(parents=True, exist_ok=True)
    Path(a.receipt).write_text(json.dumps(r, indent=2, sort_keys=True) + "\n")
    for k in ("frames_generated", "first_mismatch_frame", "first_mismatch_kind", "rgb_hash_equality",
              "score_equality", "lives_equality", "action_stream_equality", "frame_root_equality",
              "replay_from_start", "step_hash_equality", "final_mmr_equality", "recomputed_mmr_root",
              "environment_replay"):
        print(f"{k.upper()}={r[k]}")
    return 0 if r["environment_replay"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
