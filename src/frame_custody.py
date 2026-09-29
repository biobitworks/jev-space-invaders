"""Frame-level provenance: content/occurrence FCOs, frame-local Merkle, Ed25519
signing. Provenance/fingerprinting only - not DRM, not encryption of content.
Private keys never leave the local keystore directory and are never committed.
"""
from __future__ import annotations
import base64, json, os
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization
from src.fmo import hp, merkle, sha256_file

ROOT = Path(__file__).resolve().parents[1]
KEYSTORE_DIR = ROOT / ".local_keystore"  # gitignored; never committed
PRIVATE_KEY_PATH = KEYSTORE_DIR / "frame_custody_ed25519.private.pem"
PUBLIC_KEY_PATH = ROOT / "evidence" / "competition" / "frames" / "FRAME_CUSTODY_PUBLIC_KEY.pem"


def load_or_create_keypair() -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    KEYSTORE_DIR.mkdir(exist_ok=True)
    if PRIVATE_KEY_PATH.exists():
        priv = serialization.load_pem_private_key(PRIVATE_KEY_PATH.read_bytes(), password=None)
    else:
        priv = Ed25519PrivateKey.generate()
        pem = priv.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                  serialization.NoEncryption())
        PRIVATE_KEY_PATH.write_bytes(pem)
        os.chmod(PRIVATE_KEY_PATH, 0o600)
    pub = priv.public_key()
    PUBLIC_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    pub_pem = pub.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    PUBLIC_KEY_PATH.write_bytes(pub_pem)
    return priv, pub


def public_key_fingerprint(pub: Ed25519PublicKey) -> str:
    raw = pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    import hashlib
    return hashlib.sha256(raw).hexdigest()


def sign(priv: Ed25519PrivateKey, data: bytes) -> str:
    return base64.b64encode(priv.sign(data)).decode()


def verify(pub: Ed25519PublicKey, data: bytes, signature_b64: str) -> bool:
    try:
        pub.verify(base64.b64decode(signature_b64), data)
        return True
    except Exception:
        return False


def frame_content_sha256(raw_rgb_bytes: bytes) -> str:
    import hashlib
    return hashlib.sha256(raw_rgb_bytes).hexdigest()


def frame_local_atoms(frame_index: int, decision_index: int, raw_content_sha256: str, action: str,
                       score: float, lives: int, model_id: str, env_id: str, pubkey_fp: str) -> list[bytes]:
    fields = [("frame_index", frame_index), ("decision_index", decision_index),
              ("pixel_content_sha256", raw_content_sha256), ("action", action), ("score", score),
              ("lives", lives), ("model_id", model_id), ("environment_id", env_id),
              ("public_key_fingerprint", pubkey_fp)]
    return [hp("FRAME_ATOM_V1", k, v) for k, v in fields]


def frame_local_merkle_root(atoms: list[bytes]) -> str:
    return merkle(atoms).hex()


def build_frame_fcos(frame_index: int, decision_index: int, png_path: Path, raw_content_sha256: str,
                      action: str, score: float, lives: int, model_id: str, env_id: str,
                      priv: Ed25519PrivateKey, pub: Ed25519PublicKey, key_id: str) -> dict:
    pubkey_fp = public_key_fingerprint(pub)
    atoms = frame_local_atoms(frame_index, decision_index, raw_content_sha256, action, score, lives,
                               model_id, env_id, pubkey_fp)
    frame_root = frame_local_merkle_root(atoms)
    png_sha256, png_bytes = sha256_file(png_path)
    content_fco = {"fco_schema": "FrameContentFCO_V1", "frame_index": frame_index,
                    "raw_rgb_content_sha256": raw_content_sha256}
    occ_id = hp("FRAME_OCCURRENCE_V1", frame_index, raw_content_sha256, png_sha256).hex()
    sig_payload = json.dumps({"frame_index": frame_index, "content_sha256": raw_content_sha256,
                               "occurrence_id": occ_id, "frame_root": frame_root},
                              sort_keys=True, separators=(",", ":")).encode()
    occurrence_fco = {
        "fco_schema": "FrameOccurrenceFCO_V1", "frame_index": frame_index,
        "content_sha256": raw_content_sha256, "png_artifact_sha256": png_sha256,
        "png_artifact_bytes": png_bytes, "occurrence_id": occ_id, "frame_root": frame_root,
        "public_key": pub.public_bytes(serialization.Encoding.PEM,
                                        serialization.PublicFormat.SubjectPublicKeyInfo).decode(),
        "public_key_fingerprint": pubkey_fp, "key_id": key_id,
        "signature": sign(priv, sig_payload), "signature_state": "SIGNED",
    }
    breakpoint_fco = {"fco_schema": "FrameBreakpointFCO_V1", "frame_index": frame_index,
                       "frame_root": frame_root, "occurrence_id": occ_id}
    return {"content": content_fco, "occurrence": occurrence_fco, "breakpoint": breakpoint_fco,
            "frame_root": frame_root}
