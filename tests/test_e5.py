import json

import numpy as np

from experiments import e5_2p, e5_episodes
from src.deciders import Decision
from src.fmo import hp, mmr_root
from src.s01.canon import content_id


class FakeDecider:
    requested_model = "fake"

    def __init__(self, choice="FIRE"):
        self.choice, self.bodies = choice, []

    def request_body(self, ctx):
        return json.dumps({"state": ctx}).encode()

    def decide_body(self, body, prev):
        self.bodies.append(body)
        return Decision(action=self.choice if self.choice in e5_episodes.ACTIONS else prev, proposed_action=self.choice,
                        probabilities={self.choice: 1.0}, served_model="fake-openjev", model_call=True)


def test_1p_arms_differ_only_in_context_and_leaves_verify():
    runs = {}
    for arm in ("OJ", "VS"):
        d = FakeDecider()
        run, trace = e5_episodes.run_episode(arm, d, seed=1, max_decisions=25)
        runs[arm] = (run, trace, d)
        leaves = []
        for rec in trace:
            body = {k: v for k, v in rec.items() if k not in ("leaf", "ms")}
            assert hp("EPISODE_LEAF_V1", rec["t"], content_id(body)).hex() == rec["leaf"]
            leaves.append(bytes.fromhex(rec["leaf"]))
        assert mmr_root(leaves)[0] == run["episode_mmr_root"] and run["truncated"]
    oj, vs = runs["OJ"][2].bodies[5], runs["VS"][2].bodies[5]
    assert b"anticube" not in oj and b"anticube" in vs and b"path_distribution" in vs
    assert all(b"recommended" not in b for b in runs["VS"][2].bodies)
    assert runs["OJ"][1][0]["state_id"] == runs["VS"][1][0]["state_id"]   # same source state at t=0


def test_T8_ale_and_pz_ontologies_are_distinct():
    assert e5_2p.ONTOLOGY_ALE[2] == "RIGHT" and e5_2p.ONTOLOGY_PZ[2] == "UP"
    assert e5_2p.ONTOLOGY_IDS["ALE"] != e5_2p.ONTOLOGY_IDS["PZ"]
    assert set(e5_2p.QUESTION_2P["criteria"]) == set(e5_2p.ONTOLOGY_PZ)


def test_rom_gate_fails_closed(tmp_path):
    assert e5_2p.rom_gate(None)["state"] == "ROM_GATE_BLOCKED"
    assert e5_2p.rom_gate(str(tmp_path))["state"] == "ROM_GATE_BLOCKED"
    (tmp_path / "space_invaders.bin").write_bytes(b"x" * 8)
    g = e5_2p.rom_gate(str(tmp_path))
    assert g["state"] == "ROM_PRESENT" and len(g["sha256"]) == 64


def _frame(x_green, x_orange):
    f = np.zeros((210, 160, 3), np.uint8)
    f[186:190, x_green:x_green + 7] = (50, 132, 50)
    f[186:190, x_orange:x_orange + 7] = (162, 134, 56)
    return f


def test_seat_views_swap_own_and_opponent():
    f = _frame(30, 110)
    base = {"ship": None, "bombs": [], "own_shots": [], "unknown_shots": [], "aliens": {"present": False}, "shields": []}
    s0 = e5_2p.seat_state(base, f, "first_0", e5_2p.SEAT_COLOURS_DEFAULT)
    s1 = e5_2p.seat_state(base, f, "second_0", e5_2p.SEAT_COLOURS_DEFAULT)
    assert s0["own_ship"]["x"] == s1["opponent_ship"]["x"] == 33.0
    assert s1["own_ship"]["x"] == s0["opponent_ship"]["x"] == 113.0


class FakePZ:
    possible_agents = ["first_0", "second_0"]

    def __init__(self):
        self.agents, self.t = list(self.possible_agents), 0

    def reset(self, seed=None):
        return {a: _frame(30, 110) for a in self.agents}, {}

    def step(self, acts):
        self.t += 1
        done = self.t >= 4
        obs = {a: _frame(30 + self.t, 110) for a in self.agents}
        if done:
            self.agents = []
        return obs, {"first_0": 5.0, "second_0": 0.0}, {a: done for a in self.possible_agents}, {a: False for a in self.possible_agents}, {}

    def close(self):
        pass


class Fake2P(FakeDecider):
    def __init__(self):
        super().__init__("UP")


def test_2p_rows_use_2p_schema_and_pz_ontology():
    import jsonschema
    from src.perception import Perception
    summ, rows = e5_2p.run_match(FakePZ, Perception, {"first_0": Fake2P(), "second_0": Fake2P()},
                                 {"first_0": "VS", "second_0": "OJ"}, seed=1, max_decisions=10)
    schema = json.load(open("schemas/daisy/daisy_2p_row_v1.json"))
    for r in rows:
        jsonschema.validate({**r, "corpus_id": "VITHIA_E5_2P_ROWS_V1"}, schema)
        assert r["vita_action"] == "UP" and r["action_ontology_id"] == e5_2p.ONTOLOGY_IDS["PZ"]
    assert summ["relative_payoff_seat0_minus_seat1"] == 20.0 and summ["decisions"] == 4
