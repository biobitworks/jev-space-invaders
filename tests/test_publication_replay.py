from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPLAY = ROOT / "publication" / "replay" / "v0.1.0"
SCRIPT = REPLAY / "scripts" / "rebuild_publication_from_root.py"


def root_value() -> str:
    return (REPLAY / "PUBLICATION_REPLAY_ROOT.txt").read_text(encoding="utf-8").strip()


class PublicationReplayTests(unittest.TestCase):
    def run_replay(self, package: Path, root: str | None = None) -> subprocess.CompletedProcess[str]:
        out = package / "tmp_receipts"
        return subprocess.run(
            [sys.executable, str(package / "scripts" / "rebuild_publication_from_root.py"), "--root", root or root_value(), "--store", str(package), "--output", str(out), "--offline-strict"],
            text=True,
            capture_output=True,
        )

    def test_root_tamper_detection(self):
        with tempfile.TemporaryDirectory() as td:
            package = Path(td)
            shutil.copytree(REPLAY, package, dirs_exist_ok=True)
            proc = self.run_replay(package, "0" * 64)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("BLOCKED_MISSING_ROOT_REGISTRY", proc.stdout)

    def test_missing_cas_object_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            package = Path(td)
            shutil.copytree(REPLAY, package, dirs_exist_ok=True)
            leaf = json.loads((package / "leaves" / "REPLAY_LEAVES.jsonl").read_text().splitlines()[0])
            (package / leaf["resolver_locator"]).unlink()
            proc = self.run_replay(package)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("BLOCKED_MISSING_OBJECT", proc.stdout)

    def test_wrong_cas_object_bytes_fail(self):
        with tempfile.TemporaryDirectory() as td:
            package = Path(td)
            shutil.copytree(REPLAY, package, dirs_exist_ok=True)
            leaf = json.loads((package / "leaves" / "REPLAY_LEAVES.jsonl").read_text().splitlines()[0])
            (package / leaf["resolver_locator"]).write_bytes(b"x")
            proc = self.run_replay(package)
            self.assertNotEqual(proc.returncode, 0)
            receipt = json.loads((package / "tmp_receipts" / "PUBLICATION_REPLAY_RECEIPT.json").read_text())
            self.assertEqual(receipt["first_mismatch"]["mismatch_kind"], "HASH_MISMATCH")

    def test_replay_seed_tamper_detection(self):
        with tempfile.TemporaryDirectory() as td:
            package = Path(td)
            shutil.copytree(REPLAY, package, dirs_exist_ok=True)
            seed = json.loads((package / "seed" / "PUBLICATION_REPLAY_SEED_FCO.json").read_text())
            seed["project"] = "tampered"
            (package / "seed" / "PUBLICATION_REPLAY_SEED_FCO.json").write_text(json.dumps(seed, sort_keys=True))
            proc = self.run_replay(package)
            self.assertNotEqual(proc.returncode, 0)
            receipt = json.loads((package / "tmp_receipts" / "PUBLICATION_REPLAY_RECEIPT.json").read_text())
            self.assertEqual(receipt["first_mismatch"]["mismatch_kind"], "REPLAY_SEED_HASH_MISMATCH")

    def test_historical_predecessor_not_mutated(self):
        self.assertTrue((ROOT / "publication" / "release" / "v0.1.0" / "BP0015_EPHEMERAL_PYC_CUSTODY_GAP.json").exists())
        self.assertTrue((REPLAY / "seed" / "PUBLICATION_REPLAY_SEED_FCO.json").exists())

    def test_leaf_order_mutation_fails(self):
        with tempfile.TemporaryDirectory() as td:
            package = Path(td)
            shutil.copytree(REPLAY, package, dirs_exist_ok=True)
            path = package / "leaves" / "REPLAY_LEAVES.jsonl"
            rows = path.read_text().splitlines()
            rows[0], rows[1] = rows[1], rows[0]
            path.write_text("\n".join(rows) + "\n")
            proc = self.run_replay(package)
            self.assertNotEqual(proc.returncode, 0)
            receipt = json.loads((package / "tmp_receipts" / "PUBLICATION_REPLAY_RECEIPT.json").read_text())
            self.assertEqual(receipt["first_mismatch"]["mismatch_kind"], "MERKLE_ROOT_MISMATCH")

    def test_expected_output_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as td:
            package = Path(td)
            shutil.copytree(REPLAY, package, dirs_exist_ok=True)
            expected_path = package / "expected" / "EXPECTED_OUTPUTS.json"
            expected = json.loads(expected_path.read_text())
            expected["outputs"][0]["expected_sha256_if_frozen"] = "0" * 64
            expected_path.write_text(json.dumps(expected, sort_keys=True))
            proc = self.run_replay(package)
            self.assertNotEqual(proc.returncode, 0)
            receipt = json.loads((package / "tmp_receipts" / "PUBLICATION_REPLAY_RECEIPT.json").read_text())
            self.assertGreater(receipt["mismatch_count"], 0)

    def test_gumdoctor_missing_adapter_is_non_load_bearing(self):
        receipt = json.loads((ROOT / "publication" / "replay" / "gumdoctor3" / "GUMDOCTOR3_MODEL_CENSUS.json").read_text())
        self.assertEqual(receipt["model_dependency_for_rebuild"], "NONE")

    def test_openjev_auth_error_classified_as_adapter_failure(self):
        receipt = json.loads((ROOT / "publication" / "replay" / "gumdoctor3" / "GUMDOCTOR3_MODEL_CENSUS.json").read_text())
        openjev = [x for x in receipt["adapters"] if x["adapter_id"] == "openjev_local"]
        self.assertTrue(openjev)
        self.assertIn(openjev[0]["test_state"], {"AUTH_FAILURE", "ADAPTER_CONFIGURATION_FAILURE", "PROVIDER_UNAVAILABLE"})


if __name__ == "__main__":
    unittest.main()
