#!/usr/bin/env python3
"""Recompute every frame's content hash from its PNG bytes, its signature, its
frame-local Merkle root, and the ordered playthrough MMR - from scratch. A frame
is never called verified unless the PNG-decoded pixel bytes reproduce the
recorded content hash exactly.
"""
from __future__ import annotations
import base64, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PIL import Image
import numpy as np
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives import serialization
from src.fmo import mmr_root, sha256_file
from src.frame_custody import frame_content_sha256, frame_local_atoms, frame_local_merkle_root, public_key_fingerprint, verify


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
        sig_payload = json.dumps({"frame_index": i, "content_sha256": occ["content_sha256"],
                                   "occurrence_id": occ["occurrence_id"], "frame_root": occ["frame_root"]},
                                  sort_keys=True, separators=(",", ":")).encode()
        if not verify(pub, sig_payload, occ["signature"]):
            errors.append(f"SIGNATURE_INVALID:{i}")
            continue
        atoms = frame_local_atoms(i, i, occ["content_sha256"], row["action"], row["score"],
                                   row["lives"], "scripted-policy", "ALE/SpaceInvaders-v5",
                                   occ["public_key_fingerprint"])
        recomputed_frame_root = frame_local_merkle_root(atoms)
        if recomputed_frame_root != occ["frame_root"] or occ["frame_root"] != row["frame_root"]:
            errors.append(f"FRAME_ROOT_RECONSTRUCTION_MISMATCH:{i}:{recomputed_frame_root}!={occ['frame_root']}")
            continue
        leaves.append(bytes.fromhex(occ["frame_root"]))
    root, peaks = mmr_root(leaves)
    ok = not errors and root == construction["mmr_root"] and len(leaves) == construction["mmr_size"]
    out = {
        "schema": "PLAYTHROUGH_MMR_VERIFICATION_RECEIPT_V1",
        "frames_checked": len(rows),
        "errors": errors,
        "recomputed_mmr_root": root,
        "recorded_mmr_root": construction["mmr_root"],
        "PLAYTHROUGH_VERIFY": "PASS" if ok else "FAIL",
    }
    (d / "PLAYTHROUGH_MMR_VERIFICATION_RECEIPT.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
