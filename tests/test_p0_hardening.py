import json
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from scripts.qualified_breakpoint import RESERVED_FIELDS, create
from scripts.verify_competition_lineage_hardened import verify_lineage
from src.fmo import fmo_root, leaf, mmr_leaf, mmr_root, sha256_file
from src.frame_custody_final import build_frame_fcos, frame_content_sha256
from src.video_input_manifest import validate_numbered_frame_inputs


ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def build_lineage_fixture(root: Path) -> dict:
    atom_path = root / "atoms/a.txt"
    atom_path.parent.mkdir(parents=True)
    atom_path.write_text("alpha\n")
    atom_sha, atom_bytes = sha256_file(atom_path)
    atom = {
        "path": "atoms/a.txt",
        "kind": "TestAtom",
        "group": "test",
        "bytes": atom_bytes,
        "sha256": atom_sha,
        "location": "public",
        "fmo_leaf": leaf("atoms/a.txt", atom_bytes, atom_sha).hex(),
    }
    bp_root, groups = fmo_root({"test": [("atoms/a.txt", bytes.fromhex(atom["fmo_leaf"]))]})
    bp_id = "UFA-JEV-COMP-BP-0001"
    bp_file = "governance/competition/breakpoints/0001-test.json"
    bp_doc = {
        "schema": "UFA_JEV_QUALIFIED_BREAKPOINT_V1",
        "lineage_id": "UFA-JEV-COMP",
        "branch": "competition/final-integration-v01",
        "breakpoint_id": bp_id,
        "state": "TEST",
        "created_utc": "2026-09-28T00:00:00+00:00",
        "git_head_at_creation": "0" * 40,
        "root_kind": "FMO_V1_BREAKPOINT_ATOMS",
        "bp_root": bp_root,
        "breakpoint_root": bp_root,
        "parent_root": None,
        "group_roots": groups,
        "atoms": [atom],
    }
    bp_path = root / bp_file
    write_json(bp_path, bp_doc)
    bp_file_sha, _ = sha256_file(bp_path)
    mmr_leaf_hex = mmr_leaf(0, bp_id, bp_root, bp_file_sha).hex()
    mmr_root_after, peaks = mmr_root([bytes.fromhex(mmr_leaf_hex)])
    ledger = {
        "lineage_id": "UFA-JEV-COMP",
        "predecessor_roots_are_mmr_leaves": False,
        "entries": [
            {
                "seq": 0,
                "bp_id": bp_id,
                "bp_file": bp_file,
                "bp_file_sha256": bp_file_sha,
                "bp_root": bp_root,
                "branch": "competition/final-integration-v01",
                "lineage_id": "UFA-JEV-COMP",
                "parent_root": None,
                "root_kind": "FMO_V1_BREAKPOINT_ATOMS",
                "mmr_leaf": mmr_leaf_hex,
                "mmr_size": 1,
                "mmr_root_after": mmr_root_after,
                "mmr_peaks_after": peaks,
            }
        ],
    }
    ledger_path = root / "governance/lineage/UFA_JEV_COMP_MMR_LEDGER.json"
    write_json(ledger_path, ledger)
    return {"ledger": ledger, "bp_doc": bp_doc, "bp_path": bp_path, "atom_path": atom_path, "ledger_path": ledger_path}


def assert_lineage_fails(tmp_path: Path, mutator) -> None:
    fixture = build_lineage_fixture(tmp_path)
    mutator(fixture)
    _, errors = verify_lineage(tmp_path, fixture["ledger_path"])
    assert errors


def test_clean_synthetic_lineage_passes(tmp_path):
    fixture = build_lineage_fixture(tmp_path)
    _, errors = verify_lineage(tmp_path, fixture["ledger_path"])
    assert errors == []


@pytest.mark.parametrize(
    "mutator",
    [
        lambda f: (f["bp_doc"].__setitem__("breakpoint_id", "CHANGED"), write_json(f["bp_path"], f["bp_doc"])),
        lambda f: (f["bp_doc"].__setitem__("branch", "changed"), write_json(f["bp_path"], f["bp_doc"])),
        lambda f: (f["bp_doc"].__setitem__("parent_root", "0" * 64), write_json(f["bp_path"], f["bp_doc"])),
        lambda f: (f["bp_doc"].__setitem__("bp_root", "0" * 64), write_json(f["bp_path"], f["bp_doc"])),
        lambda f: (f["bp_doc"].__setitem__("breakpoint_root", "1" * 64), write_json(f["bp_path"], f["bp_doc"])),
        lambda f: (f["ledger"]["entries"][0].__setitem__("bp_file_sha256", "0" * 64), write_json(f["ledger_path"], f["ledger"])),
        lambda f: f["atom_path"].write_text("changed\n"),
        lambda f: (f["bp_doc"]["atoms"][0].__setitem__("bytes", 999), write_json(f["bp_path"], f["bp_doc"])),
        lambda f: (f["bp_doc"]["atoms"][0].__setitem__("path", "atoms/missing.txt"), write_json(f["bp_path"], f["bp_doc"])),
        lambda f: (f["ledger"]["entries"][0].__setitem__("mmr_leaf", "0" * 64), write_json(f["ledger_path"], f["ledger"])),
        lambda f: (f["ledger"]["entries"][0].__setitem__("mmr_root_after", "0" * 64), write_json(f["ledger_path"], f["ledger"])),
        lambda f: (f["ledger"]["entries"].append(dict(f["ledger"]["entries"][0])), write_json(f["ledger_path"], f["ledger"])),
        lambda f: (f["ledger"]["entries"].append({**f["ledger"]["entries"][0], "seq": 1}), write_json(f["ledger_path"], f["ledger"])),
    ],
)
def test_lineage_adversarial_fixture_fails(tmp_path, mutator):
    assert_lineage_fails(tmp_path, mutator)


@pytest.mark.parametrize("field", sorted(RESERVED_FIELDS))
def test_reserved_breakpoint_fields_fail_closed(field):
    with pytest.raises(ValueError):
        create("reserved-field-test", "TEST", [], {field: "caller"})


def build_frame_fixture(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    raw = bytes([0, 0, 0, 255, 255, 255, 1, 2, 3])
    Image.frombytes("RGB", (3, 1), raw).save(directory / "frame_0000.png")
    priv = Ed25519PrivateKey.generate()
    pub = priv.public_key()
    fcos = build_frame_fcos(
        0,
        0,
        directory / "frame_0000.png",
        frame_content_sha256(raw),
        "NOOP",
        0.0,
        3,
        "test-model",
        "test-env",
        priv,
        pub,
        "test-key",
    )
    write_json(directory / "frame_0000.occurrence.json", fcos["occurrence"])
    (directory / "FRAME_BREAKPOINT_LEAVES.jsonl").write_text(
        json.dumps({"frame_index": 0, "decision_index": 0, "action": "NOOP", "score": 0.0, "lives": 3, "model_id": "test-model", "environment_id": "test-env", "frame_root": fcos["frame_root"]}) + "\n"
    )
    write_json(directory / "PLAYTHROUGH_MMR_CONSTRUCTION_RECEIPT.json", {"mmr_root": fcos["frame_root"], "mmr_size": 1})


def run_frame_verifier(directory: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts/verify_final_playthrough_custody_hardened.py"), str(directory)],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )


def mutate_occurrence(directory: Path, mutator) -> None:
    path = directory / "frame_0000.occurrence.json"
    data = json.loads(path.read_text())
    mutator(data)
    write_json(path, data)


def test_valid_key_valid_fingerprint_passes(tmp_path):
    build_frame_fixture(tmp_path)
    assert run_frame_verifier(tmp_path).returncode == 0


def test_valid_key_wrong_fingerprint_fails(tmp_path):
    build_frame_fixture(tmp_path)
    mutate_occurrence(tmp_path, lambda d: d.__setitem__("public_key_fingerprint", "0" * 64))
    assert run_frame_verifier(tmp_path).returncode != 0


def test_mutated_key_recorded_old_fingerprint_fails(tmp_path):
    build_frame_fixture(tmp_path)
    new_pub = Ed25519PrivateKey.generate().public_key()
    from cryptography.hazmat.primitives import serialization

    new_pem = new_pub.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    mutate_occurrence(tmp_path, lambda d: d.__setitem__("public_key", new_pem))
    assert run_frame_verifier(tmp_path).returncode != 0


def test_missing_public_key_fails(tmp_path):
    build_frame_fixture(tmp_path)
    mutate_occurrence(tmp_path, lambda d: d.pop("public_key"))
    assert run_frame_verifier(tmp_path).returncode != 0


def test_missing_fingerprint_fails(tmp_path):
    build_frame_fixture(tmp_path)
    mutate_occurrence(tmp_path, lambda d: d.pop("public_key_fingerprint"))
    assert run_frame_verifier(tmp_path).returncode != 0


def write_frame(path: Path) -> None:
    path.write_bytes(b"not an actual png for manifest-only tests")


def test_bounded_ffmpeg_input_manifest_accepts_strict_interval(tmp_path):
    write_frame(tmp_path / "frame_0000.png")
    write_frame(tmp_path / "frame_0001.png")
    manifest = validate_numbered_frame_inputs(tmp_path, 2)
    assert manifest["first_frame"] == "frame_0000.png"
    assert manifest["last_frame"] == "frame_0001.png"
    assert manifest["expected_frame_count"] == 2
    assert manifest["actual_frame_count"] == 2


def test_bounded_ffmpeg_input_manifest_gap_fails(tmp_path):
    write_frame(tmp_path / "frame_0000.png")
    write_frame(tmp_path / "frame_0002.png")
    with pytest.raises(ValueError):
        validate_numbered_frame_inputs(tmp_path, 3)


def test_bounded_ffmpeg_input_manifest_extra_frame_fails(tmp_path):
    write_frame(tmp_path / "frame_0000.png")
    write_frame(tmp_path / "frame_0001.png")
    write_frame(tmp_path / "frame_0002.png")
    with pytest.raises(ValueError):
        validate_numbered_frame_inputs(tmp_path, 2)
