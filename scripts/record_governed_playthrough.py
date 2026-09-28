#!/usr/bin/env python3
"""Bounded governed-playthrough recorder: captures N frames from a scripted-policy
episode, wraps each in content/occurrence/breakpoint FCOs (src/frame_custody.py),
and builds the ordered playthrough MMR. SETUP_SMOKE / NON_SUBMISSION /
NON_EXPERIMENTAL by default - not a counted results.json run, not the final demo.
"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image
from src.envcfg import make_env, ENV_CONFIG
from src.perception import Perception
from src.actions import ACTION_TO_ID
from src.fmo import mmr_leaf, mmr_root
from src.frame_custody import load_or_create_keypair, frame_content_sha256, build_frame_fcos, public_key_fingerprint


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--max-frames", type=int, default=24)
    ap.add_argument("--out-dir", default=str(ROOT / "evidence/competition/frames/smoke"))
    ap.add_argument("--label", default="SETUP_SMOKE")
    a = ap.parse_args()

    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    priv, pub = load_or_create_keypair()
    key_id = "frame-custody-ed25519-v1"

    env = make_env()
    perception = Perception()
    obs, info = env.reset(seed=a.seed)
    score, prev = 0.0, "NOOP"
    period = 30

    fcos, leaves, rows = [], [], []
    for i in range(a.max_frames):
        a_choice = "RIGHTFIRE" if (i // period) % 2 == 0 else "LEFTFIRE"
        raw_bytes = obs.tobytes()
        content_sha = frame_content_sha256(raw_bytes)
        png_path = out / f"frame_{i:04d}.png"
        Image.fromarray(obs).save(png_path)
        fco = build_frame_fcos(i, i, png_path, content_sha, a_choice, score, int(info.get("lives", 0)),
                                model_id="scripted-policy", env_id=ENV_CONFIG["env_id"],
                                priv=priv, pub=pub, key_id=key_id)
        fcos.append(fco)
        leaves.append(bytes.fromhex(fco["frame_root"]))
        rows.append({"frame_index": i, "frame_root": fco["frame_root"],
                     "occurrence_id": fco["occurrence"]["occurrence_id"], "action": a_choice,
                     "score": score, "lives": int(info.get("lives", 0))})
        obs, r, term, trunc, info = env.step(ACTION_TO_ID[a_choice])
        score += float(r)
        prev = a_choice
        if term or trunc:
            break
    env.close()

    leaves_path = out / "FRAME_BREAKPOINT_LEAVES.jsonl"
    leaves_path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows))

    proot, peaks = mmr_root(leaves)
    construction = {
        "schema": "PLAYTHROUGH_MMR_CONSTRUCTION_RECEIPT_V1",
        "label": a.label,
        "seed": a.seed,
        "frame_count": len(rows),
        "leaves_file": str(leaves_path.relative_to(ROOT)),
        "mmr_size": len(leaves),
        "mmr_peaks": peaks,
        "mmr_root": proot,
        "public_key_fingerprint": public_key_fingerprint(pub),
        "key_id": key_id,
        "final_score": score,
    }
    (out / "PLAYTHROUGH_MMR_CONSTRUCTION_RECEIPT.json").write_text(json.dumps(construction, indent=2) + "\n")

    for fco in fcos:
        occ_path = out / f"frame_{fco['occurrence']['frame_index']:04d}.occurrence.json"
        occ_path.write_text(json.dumps(fco["occurrence"], indent=2) + "\n")

    print(json.dumps(construction, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
