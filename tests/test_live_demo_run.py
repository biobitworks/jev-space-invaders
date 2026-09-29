from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import live_demo.run as runmod
from live_demo.run import (
    ROOT,
    _classify_decider,
    _mmr_root,
    _preprocessor,
    _sha,
    build_parser,
    run,
    run_openjev_ab,
)


class LiveDemoRunTests(unittest.TestCase):
    def test_flag_normalization(self):
        self.assertEqual(_preprocessor("none"), "NONE")
        self.assertEqual(_preprocessor("vithia"), "VITHIA_SPACE")
        self.assertEqual(_classify_decider("scripted"), ("SCRIPTED_BASELINE", "scripted-policy", "scripted-policy"))
        self.assertEqual(_classify_decider("ollama:qwen2.5:0.5b"), ("OLLAMA", "qwen2.5:0.5b", "qwen2.5:0.5b"))
        self.assertEqual(_classify_decider("openjev_local"), ("SYSTEM_ONE", "OPENJEV_LOCAL", "openjev"))

    def test_cli_1p_writes_trace_and_results_after_real_env_step(self):
        with tempfile.TemporaryDirectory() as td:
            results_path = Path(td) / "results.json"
            trace_dir = Path(td) / "traces"
            args = build_parser().parse_args([
                "--mode", "1p",
                "--seed", "11",
                "--steps", "1",
                "--episodes", "1",
                "--player0-preprocessor", "none",
                "--player0-decider", "scripted",
                "--results-path", str(results_path),
                "--trace-dir", str(trace_dir),
                "--headless",
                "--run-class", "SCRIPTED_CONTROL",
            ])
            row = run(args)
            self.assertEqual(row["terminal_acceptance"], "PASS")
            self.assertEqual(row["mode"], "1P")
            self.assertEqual(row["steps_executed"], 1)
            self.assertEqual(row["eca_6_class"], "PASS")

            doc = json.loads(results_path.read_text())
            self.assertEqual(doc["terminal_runs"][-1]["run_id"], row["run_id"])
            trace = Path(row["trace_file"])
            if not trace.is_absolute():
                trace = ROOT / trace
            trace_rows = [json.loads(line) for line in trace.read_text().splitlines()]
            self.assertEqual(len(trace_rows), 1)
            self.assertTrue(trace_rows[0]["environment_action_executed"])
            self.assertIn(trace_rows[0]["executed_action"], {"NOOP", "FIRE", "LEFT", "LEFTFIRE", "RIGHT", "RIGHTFIRE"})
            self.assertIn("fco_trace", trace_rows[0])

    def test_mmr_root_changes_with_order(self):
        leaves = [_sha({"leaf": i}) for i in range(3)]
        self.assertEqual(_mmr_root(leaves), _mmr_root(list(leaves)))
        self.assertNotEqual(_mmr_root(leaves), _mmr_root(list(reversed(leaves))))

    def test_openjev_ab_blocked_receipt_when_not_loaded(self):
        with tempfile.TemporaryDirectory() as td:
            args = build_parser().parse_args([
                "--benchmark-pair-openjev",
                "--seeds", "1",
                "--max-steps", "1",
                "--output-dir", td,
                "--results-path", str(Path(td) / "results.json"),
            ])
            with patch.object(runmod, "_openjev_status", return_value={"OPENJEV_LOAD_STATE": "BLOCKED_NOT_LOADED"}):
                receipt = run_openjev_ab(args)
            self.assertEqual(receipt["RAW_OPENJEV_1P"], "BLOCKED_OPENJEV_NOT_LOADED")
            self.assertTrue(any(Path(td).glob("run_*/manifest.json")))


if __name__ == "__main__":
    unittest.main()
