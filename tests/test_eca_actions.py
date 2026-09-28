from __future__ import annotations

import unittest

from src.eca_actions import ECA_ACTIONS, ECA_CLASSES, compose, decompose, round_trip
from src.envcfg import make_env


class ECAActionTests(unittest.TestCase):
    def test_exact_mapping_round_trip_uniqueness_and_completeness(self):
        expected = {
            ("NONE", "NO"): "NOOP", ("NONE", "YES"): "FIRE",
            ("LEFT", "NO"): "LEFT", ("LEFT", "YES"): "LEFTFIRE",
            ("RIGHT", "NO"): "RIGHT", ("RIGHT", "YES"): "RIGHTFIRE",
        }
        self.assertEqual(dict(((m, f), a) for m, f, a in ECA_CLASSES), expected)
        self.assertEqual(set(ECA_ACTIONS), set(expected.values()))
        self.assertEqual(len(ECA_ACTIONS), 6)
        self.assertEqual(len(set(ECA_ACTIONS)), 6)
        for (move, fire), action in expected.items():
            self.assertEqual(compose(move, fire), action)
            self.assertEqual(decompose(action), (move, fire))
            self.assertEqual(round_trip(action), action)

    def test_every_class_executes_a_real_ale_transition(self):
        env = make_env()
        try:
            for index, action in enumerate(ECA_ACTIONS):
                env.reset(seed=100 + index)
                before = env.unwrapped.ale.getFrameNumber()
                env.step({"NOOP": 0, "FIRE": 1, "RIGHT": 2, "LEFT": 3, "RIGHTFIRE": 4, "LEFTFIRE": 5}[action])
                after = env.unwrapped.ale.getFrameNumber()
                self.assertGreater(after, before, action)
        finally:
            env.close()


if __name__ == "__main__":
    unittest.main()
