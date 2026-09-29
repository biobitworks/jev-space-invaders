from __future__ import annotations

import json
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from demo.live_demo import DemoController, OllamaDecider, PZ_ACTIONS, serve


def fake_decide(self, state, mode):
    action = "FIRE" if mode == "1P_ALE" else ("LEFT" if state.get("seat") == "first_0" else "RIGHT")
    return {"requested_action": action, "executed_action": action, "projected_plan": [action, "NOOP"],
            "confidence": None, "reason": "test", "fallback": False, "latency_ms": 0.1,
            "backend": f"test:{self.model}", "model_call": True}


class LiveDemoTests(unittest.TestCase):
    def test_loopback_server_binds_localhost(self):
        with tempfile.TemporaryDirectory() as td:
            server = serve("127.0.0.1", 0, td)
            try:
                self.assertEqual(server.server_address[0], "127.0.0.1")
            finally:
                server.controller._close_envs()
                server.server_close()

    def test_1p_pause_and_exact_step(self):
        with tempfile.TemporaryDirectory() as td, patch.object(OllamaDecider, "decide", fake_decide):
            c = DemoController(td)
            try:
                self.assertEqual(c.mode, "1P")
                self.assertEqual(c.status, "paused")
                before = c.state()["decision_index"]
                c.pause()
                self.assertEqual(c.state()["decision_index"], before)
                c.step_once()
                self.assertEqual(c.state()["decision_index"], before + 1)
                row = json.loads(next(Path(td).glob("*.jsonl")).read_text().splitlines()[-1])
                self.assertEqual(row["mode"], "1P")
                self.assertEqual(row["executed_action"], "FIRE")
                self.assertNotIn("recommended_action", row)
            finally:
                c._close_envs()

    @unittest.skipUnless(importlib.util.find_spec("pettingzoo"), "PettingZoo is supplied by the dedicated 2P runtime")
    def test_2p_is_one_joint_transition(self):
        with tempfile.TemporaryDirectory() as td, patch.object(OllamaDecider, "decide", fake_decide):
            c = DemoController(td)
            try:
                c.set_mode("2P")
                before = c.state()
                c.step_once()
                after = c.state()
                self.assertEqual(after["decision_index"], before["decision_index"] + 2)
                self.assertEqual(after["joint_step"], before["joint_step"] + 1)
                files = list(Path(td).glob("*.jsonl"))
                row = next(json.loads(line) for path in files for line in path.read_text().splitlines()
                           if json.loads(line).get("mode") == "2P" and "joint_transition_executed" in json.loads(line))
                self.assertEqual(row["mode"], "2P")
                self.assertTrue(row["joint_transition_executed"])
                self.assertIn(row["player0"]["executed_action"], PZ_ACTIONS)
                self.assertIn(row["player1"]["executed_action"], PZ_ACTIONS)
            finally:
                c._close_envs()

    def test_invalid_model_output_is_never_executed(self):
        def invalid(self, state, mode):
            return {"requested_action": "RIGHTFIRE", "executed_action": "NOOP", "projected_plan": [],
                    "confidence": None, "reason": "invalid_model_output_held_to_noop", "fallback": True,
                    "latency_ms": 0.1, "backend": "test:invalid", "model_call": True}
        with tempfile.TemporaryDirectory() as td, patch.object(OllamaDecider, "decide", invalid):
            c = DemoController(td)
            try:
                c.step_once()
                row = json.loads(next(Path(td).glob("*.jsonl")).read_text().splitlines()[-1])
                self.assertEqual(row["requested_action"], "RIGHTFIRE")
                self.assertEqual(row["executed_action"], "NOOP")
                self.assertTrue(row["fallback"])
            finally:
                c._close_envs()


if __name__ == "__main__":
    unittest.main()
