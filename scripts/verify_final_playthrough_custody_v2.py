#!/usr/bin/env python3
"""v2 of verify_final_playthrough_custody.py (immutable atom of
UFA-JEV-COMP-BP-0012, not edited in place). Same fix as
verify_playthrough_custody_v2.py: require the loaded key's fingerprint to
match both the occurrence and construction receipt's recorded fingerprint
before trusting a signature. See that file's docstring for the known
remaining limitation (per-playthrough key, not one globally published key).
"""
from __future__ import annotations
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image
import numpy as np
from cryptography.hazmat.primitives import serialization
from src.fmo import mmr_root, sha256_file
from src.frame_custody_final import frame_content_sha256, frame_local_atoms, frame_local_merkle_root, public_key_fingerprint, verify


def main() -> int:
    d = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "evidence/competition/frames/smoke")
    construction = json.loads((d / "PLAYTHROUGH_MMR_CONSTRUCTION_RECEIPT.json").read_text())
    rows = [json.loads(l) for l in (d / "FRAME_BREAKPOINT_LEAVES.jsonl").read_text().splitlines()]
    errors = []
    leaves = []
    for row in rows:
        i = row["frame_index"]
        occ = json.loads((d / f"frame_{i:04d}.occurrence.json").read_text())
        png_path = d / f"frame_{i:04d}.png"
        png_sha, png_bytes = sha256_file(png_path)
        if png_sha != occ["png_artifact_sha256"]:
            errors.append(f"PNG_BYTES_CHANGED:{i}")
            continue
        decoded = np.array(Image.open(png_path).convert("RGB"))
        recon_sha = frame_content_sha256(decoded.tobytes())
        if recon_sha != occ["content_sha256"]:
            errors.append(f"CONTENT_RECONSTRUCTION_MISMATCH:{i}:{recon_sha}!={occ['content_sha256']}")
            continue
        pub = serialization.load_pem_public_key(occ["public_key"].encode())
        loaded_fp = public_key_fingerprint(pub)
        if loaded_fp != occ["public_key_fingerprint"] or loaded_fp != construction["public_key_fingerprint"]:
            errors.append(f"PUBLIC_KEY_FINGERPRINT_MISMATCH:{i}:{loaded_fp}")
            continue
        sig_payload = json.dumps({"frame_index": i, "content_sha256": occ["content_sha256"],
                                   "occurrence_id": occ["occurrence_id"], "frame_root": occ["frame_root"]},
                                  sort_keys=True, separators=(",", ":")).encode()
        if not verify(pub, sig_payload, occ["signature"]):
            errors.append(f"SIGNATURE_INVALID:{i}")
            continue
        decision_index = occ.get("decision_index", row.get("decision_index", i))
        action = occ.get("action", row["action"])
        score = occ.get("score", row["score"])
        lives = occ.get("lives", row["lives"])
        model_id = occ.get("model_id", row.get("model_id", "scripted-policy"))
        env_id = occ.get("environment_id", row.get("environment_id", "ALE/SpaceInvaders-v5"))
        atoms = frame_local_atoms(i, decision_index, occ["content_sha256"], action, score,
                                   lives, model_id, env_id, occ["public_key_fingerprint"])
        recomputed_frame_root = frame_local_merkle_root(atoms)
        if recomputed_frame_root != occ["frame_root"] or occ["frame_root"] != row["frame_root"]:
            errors.append(f"FRAME_ROOT_RECONSTRUCTION_MISMATCH:{i}:{recomputed_frame_root}!={occ['frame_root']}")
            continue
        leaves.append(bytes.fromhex(occ["frame_root"]))
    root, peaks = mmr_root(leaves)
    ok = not errors and root == construction["mmr_root"] and len(leaves) == construction["mmr_size"]
    out = {
        "schema": "PLAYTHROUGH_MMR_VERIFICATION_RECEIPT_V2",
        "frames_checked": len(rows),
        "errors": errors,
        "recomputed_mmr_root": root,
        "recorded_mmr_root": construction["mmr_root"],
        "public_key_fingerprint_checked": True,
        "PLAYTHROUGH_VERIFY": "PASS" if ok else "FAIL",
    }
    (d / "PLAYTHROUGH_MMR_VERIFICATION_RECEIPT_V2.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
