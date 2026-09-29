from __future__ import annotations

import importlib.util
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path

from demo.live_demo import DemoController, JEVApiSystemOne, OpenJEVLocalSystemOne, PZ_ACTIONS, ScriptedDecider, serve


class LiveDemoTests(unittest.TestCase):
    def test_system_one_backend_identity(self):
        with tempfile.TemporaryDirectory() as td:
            c = DemoController(td)
            try:
                c.set_seat("PLAYER_0", {"decider_provider": "SYSTEM_ONE", "decider_backend": "OPENJEV_LOCAL"})
                backend = c.registry.decider(c.seats["PLAYER_0"], tuple(ALE for ALE in ("NOOP", "FIRE")))
                self.assertIsInstance(backend, OpenJEVLocalSystemOne)
                self.assertTrue(backend.system_one)
            finally: c._close_envs()

    def test_jev_api_requires_typesafe_key(self):
        with unittest.mock.patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "BLOCKED_MISSING_TYPESAFE_API_KEY"):
                JEVApiSystemOne("JEV_API_REMOTE", "JEV", ("NOOP", "FIRE"), "https://api.typesafe.ai", "jev")

    def test_loopback_server_binds_localhost(self):
        with tempfile.TemporaryDirectory() as td:
            server = serve("127.0.0.1", 0, td)
            try: self.assertEqual(server.server_address[0], "127.0.0.1")
            finally: server.controller._close_envs(); server.server_close()

    def test_per_seat_config_and_exact_1p_step(self):
        with tempfile.TemporaryDirectory() as td:
            c = DemoController(td)
            try:
                c.set_seat("PLAYER_0", {"preprocessor": "NONE", "decider_provider": "SCRIPTED_BASELINE", "decider_backend": "scripted-policy", "exact_model": "scripted-policy"})
                before = c.state()["decision_index"]; c.step_once(); after = c.state()
                self.assertEqual(after["decision_index"], before + 1)
                row = next(json.loads(line) for path in Path(td).glob("*.jsonl") for line in path.read_text().splitlines() if json.loads(line).get("mode") == "1P" and json.loads(line).get("env_advanced"))
                self.assertEqual(row["preprocessor_actual"], "NONE"); self.assertEqual(row["decider_provider"], "SCRIPTED_BASELINE"); self.assertTrue(row["env_advanced"])
            finally: c._close_envs()

    @unittest.skipUnless(importlib.util.find_spec("pettingzoo"), "PettingZoo is supplied by the dedicated 2P runtime")
    def test_2p_is_two_decisions_one_joint_transition(self):
        with tempfile.TemporaryDirectory() as td:
            c = DemoController(td)
            try:
                c.set_mode("2P"); c.set_seat("PLAYER_0", {"decider_provider": "SCRIPTED_BASELINE", "decider_backend": "scripted-policy", "exact_model": "scripted-policy"}); c.set_seat("PLAYER_1", {"decider_provider": "SCRIPTED_BASELINE", "decider_backend": "scripted-policy", "exact_model": "scripted-policy"})
                before = c.state(); c.step_once(); after = c.state()
                self.assertEqual(after["decision_index"], before["decision_index"] + 2); self.assertEqual(after["joint_step"], before["joint_step"] + 1)
                row = next(json.loads(line) for path in Path(td).glob("*.jsonl") for line in path.read_text().splitlines() if json.loads(line).get("joint_transition_executed"))
                self.assertTrue(row["joint_transition_executed"]); self.assertIn(row["player0"]["executed_action"], PZ_ACTIONS); self.assertIn(row["player1"]["executed_action"], PZ_ACTIONS)
            finally: c._close_envs()

    def test_stale_result_is_discarded_after_pause(self):
        with tempfile.TemporaryDirectory() as td:
            c = DemoController(td); started = threading.Event(); release = threading.Event()
            class Slow(ScriptedDecider):
                def decide(self, state, mode, previous):
                    started.set(); release.wait(2); return super().decide(state, mode, previous)
            c.registry.decider = lambda cfg, actions: Slow(cfg.decider_provider, cfg.decider_backend, actions)
            worker = threading.Thread(target=c.step_once); worker.start(); self.assertTrue(started.wait(1)); c.pause(); release.set(); worker.join(3)
            self.assertEqual(c.state()["frame_index"], 0)
            self.assertTrue(any("DISCARD_STALE_RESULT" in line for p in Path(td).glob("*.jsonl") for line in p.read_text().splitlines()))
            c._close_envs()


if __name__ == "__main__": unittest.main()
