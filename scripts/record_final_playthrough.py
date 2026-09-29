#!/usr/bin/env python3
"""Bounded governed-playthrough recorder: captures N frames from a scripted-policy
episode, wraps each in content/occurrence/breakpoint FCOs (src/frame_custody.py),
and builds the ordered playthrough MMR. SETUP_SMOKE / NON_SUBMISSION /
NON_EXPERIMENTAL by default - not a counted results.json run, not the final demo.
"""
from __future__ import annotations
import argparse, json, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image
from src.envcfg import make_env, ENV_CONFIG, K
from src.actions import ACTION_TO_ID
from src.fmo import mmr_leaf, mmr_root
from src.frame_custody_final import load_or_create_keypair, frame_content_sha256, build_frame_fcos, public_key_fingerprint


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--max-frames", type=int, default=24)
    ap.add_argument("--max-decisions", type=int, default=None)
    ap.add_argument("--out-dir", default=str(ROOT / "evidence/competition/frames/smoke"))
    ap.add_argument("--label", default="SETUP_SMOKE")
    ap.add_argument("--capture-mode", choices=("decision", "actual-ale"), default="decision")
    a = ap.parse_args()

    out = Path(a.out_dir)
    if not out.is_absolute():
        out = ROOT / out
    out.mkdir(parents=True, exist_ok=True)
    priv, pub = load_or_create_keypair()
    key_id = "frame-custody-ed25519-v1"

    score, prev = 0.0, "NOOP"
    period = 30

    fcos, leaves, rows = [], [], []
    decision_latencies_ms, end_to_end_latencies_ms = [], []
    wall_start = time.perf_counter()

    def capture_frame(frame_index: int, decision_index: int, obs, action: str, score_now: float, lives: int):
        frame_start = time.perf_counter()
        raw_bytes = obs.tobytes()
        content_sha = frame_content_sha256(raw_bytes)
        png_path = out / f"frame_{frame_index:04d}.png"
        Image.fromarray(obs).save(png_path)
        fco = build_frame_fcos(frame_index, decision_index, png_path, content_sha, action, score_now, lives,
                                model_id="scripted-policy", env_id=ENV_CONFIG["env_id"],
                                priv=priv, pub=pub, key_id=key_id)
        fcos.append(fco)
        leaves.append(bytes.fromhex(fco["frame_root"]))
        rows.append({"frame_index": frame_index, "decision_index": decision_index,
                     "frame_root": fco["frame_root"],
                     "occurrence_id": fco["occurrence"]["occurrence_id"], "action": action,
                     "score": score_now, "lives": lives, "model_id": "scripted-policy",
                     "environment_id": ENV_CONFIG["env_id"]})
        end_to_end_latencies_ms.append((time.perf_counter() - frame_start) * 1000.0)

    if a.capture_mode == "decision":
        env = make_env()
        obs, info = env.reset(seed=a.seed)
        frame_count_limit = a.max_frames
        for i in range(frame_count_limit):
            decision_start = time.perf_counter()
            a_choice = "RIGHTFIRE" if (i // period) % 2 == 0 else "LEFTFIRE"
            decision_latencies_ms.append((time.perf_counter() - decision_start) * 1000.0)
            capture_frame(i, i, obs, a_choice, score, int(info.get("lives", 0)))
            obs, r, term, trunc, info = env.step(ACTION_TO_ID[a_choice])
            score += float(r)
            prev = a_choice
            if term or trunc:
                break
        env.close()
    else:
        import ale_py
        import gymnasium as gym

        gym.register_envs(ale_py)
        env = gym.make(ENV_CONFIG["env_id"], obs_type=ENV_CONFIG["obs_type"], frameskip=1,
                       repeat_action_probability=ENV_CONFIG["repeat_action_probability"],
                       full_action_space=ENV_CONFIG["full_action_space"],
                       max_num_frames_per_episode=ENV_CONFIG["max_num_frames_per_episode"])
        meanings = tuple(env.unwrapped.get_action_meanings())
        if meanings != tuple(ACTION_TO_ID.keys()):
            raise RuntimeError(f"ALE action set {meanings} != expected {tuple(ACTION_TO_ID.keys())}")
        obs, info = env.reset(seed=a.seed)
        frame_index = 0
        decision_index = 0
        term = trunc = False
        max_decisions = a.max_decisions if a.max_decisions is not None else max(1, (a.max_frames + K - 1) // K)
        while frame_index < a.max_frames and decision_index < max_decisions and not (term or trunc):
            decision_start = time.perf_counter()
            a_choice = "RIGHTFIRE" if (decision_index // period) % 2 == 0 else "LEFTFIRE"
            decision_latencies_ms.append((time.perf_counter() - decision_start) * 1000.0)
            for _ in range(K):
                if frame_index >= a.max_frames or term or trunc:
                    break
                capture_frame(frame_index, decision_index, obs, a_choice, score, int(info.get("lives", 0)))
                obs, r, term, trunc, info = env.step(ACTION_TO_ID[a_choice])
                score += float(r)
                frame_index += 1
            prev = a_choice
            decision_index += 1
        env.close()

    wall_seconds = time.perf_counter() - wall_start

    leaves_path = out / "FRAME_BREAKPOINT_LEAVES.jsonl"
    leaves_path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))

    proot, peaks = mmr_root(leaves)
    construction = {
        "schema": "PLAYTHROUGH_MMR_CONSTRUCTION_RECEIPT_V1",
        "label": a.label,
        "seed": a.seed,
        "frame_count": len(rows),
        "capture_mode": a.capture_mode,
        "decision_count": len(decision_latencies_ms),
        "leaves_file": str(leaves_path.relative_to(ROOT)),
        "mmr_size": len(leaves),
        "mmr_peaks": peaks,
        "mmr_root": proot,
        "public_key_fingerprint": public_key_fingerprint(pub),
        "key_id": key_id,
        "final_score": score,
        "wall_seconds": wall_seconds,
    }
    (out / "PLAYTHROUGH_MMR_CONSTRUCTION_RECEIPT.json").write_text(json.dumps(construction, indent=2) + "\n")

    def percentile(values, pct):
        if not values:
            return None
        ordered = sorted(values)
        idx = min(len(ordered) - 1, max(0, round((pct / 100.0) * (len(ordered) - 1))))
        return ordered[idx]

    telemetry = {
        "schema": "PLAYTHROUGH_TELEMETRY_V1",
        "label": a.label,
        "seed": a.seed,
        "capture_mode": a.capture_mode,
        "frame_count": len(rows),
        "decision_count": len(decision_latencies_ms),
        "nominal_game_fps": 60,
        "simulated_seconds": len(rows) / 60.0,
        "wall_seconds": wall_seconds,
        "effective_fps": len(rows) / wall_seconds if wall_seconds else None,
        "real_time_factor": (len(rows) / 60.0) / wall_seconds if wall_seconds else None,
        "decisions_per_second": len(decision_latencies_ms) / wall_seconds if wall_seconds else None,
        "decision_latency_ms_p50": percentile(decision_latencies_ms, 50),
        "decision_latency_ms_p95": percentile(decision_latencies_ms, 95),
        "end_to_end_latency_ms_p50": percentile(end_to_end_latencies_ms, 50),
        "end_to_end_latency_ms_p95": percentile(end_to_end_latencies_ms, 95),
        "deadline_miss_rate": "NOT_APPLICABLE_NO_DEADLINE_DEFINED",
        "input_tokens": "NOT_APPLICABLE_SCRIPTED_POLICY",
        "output_tokens": "NOT_APPLICABLE_SCRIPTED_POLICY",
    }
    (out / "PLAYTHROUGH_TELEMETRY.json").write_text(json.dumps(telemetry, indent=2) + "\n")

    for fco in fcos:
        occ_path = out / f"frame_{fco['occurrence']['frame_index']:04d}.occurrence.json"
        occ_path.write_text(json.dumps(fco["occurrence"], indent=2) + "\n")

    print(json.dumps(construction, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
