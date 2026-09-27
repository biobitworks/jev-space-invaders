"""TYPE_ERROR_T1..T7 (see vita01/TYPE_ERROR_TEST_REGISTRY.json)."""
import hashlib
import random

import gymnasium as gym
import numpy as np

from src.fmo import fmo_root, leaf
from src.kernels import life
from src.kernels.eca import evolve
from src.s01.canon import content_id
from src.vita01 import typecheck as tc


def _glider_history(n=9):
    g = life.place(life.parse(life.CATALOGUE_CELLS["glider"]), 24, 24, 4, 4)
    hist = [g]
    for _ in range(n - 1):
        hist.append(life.step(hist[-1]))
    return hist


def test_T1_identity_is_not_meaning():
    hist = _glider_history()
    cur = hist[-1]
    atom = {"kind": "SourceAtomFCO", "bits_hex": np.packbits(cur).tobytes().hex()}
    ctx_hist = {"kinematics": life.kinematics(hist)}
    ctx_none = {"kinematics": life.kinematics([cur])}
    assert content_id(atom) == content_id(dict(atom))          # same identity
    assert ctx_hist != ctx_none                                  # different meaning
    assert tc.check_identity_vs_meaning(content_id(atom), content_id(atom), ctx_hist, ctx_none)["verdict"] == "ALLOW"


def test_T2_prediction_is_not_observation():
    pred = {"id": "p1", "observation_status": "PREDICTED"}
    assert tc.check_observation_promotion(pred, "OBSERVED", None)["verdict"] == "REJECT"
    assert tc.check_observation_promotion(pred, "OBSERVED", {"kind": "ObservationReceipt", "source_id": "p1"})["verdict"] == "REJECT"
    assert tc.check_observation_promotion(pred, "OBSERVED", {"kind": "ObservationReceipt", "source_id": "env:step42"})["verdict"] == "ALLOW"
    import jsonschema
    import pytest
    from src.s01.protocol import validate
    with pytest.raises(jsonschema.ValidationError):   # a predicted successor cannot pass as a transition receipt
        validate({"schema": "S01_TRANSITION_RECEIPT_V1", "packet_id": "x", "action": "L", "successor_atoms": [],
                  "observation_status": "PREDICTED", "observation_receipt": {"kind": "Prediction", "source": "model"}},
                 "S01_TRANSITION_RECEIPT_V1")


def test_T3_simulation_is_not_wet_lab():
    sim = {"evidence_level": "SIMULATED"}
    for lvl in ("IN_VITRO", "IN_VIVO", "CLINICAL"):
        assert tc.check_evidence_promotion(sim, lvl, None)["verdict"] == "REJECT"
        assert tc.check_evidence_promotion(sim, lvl, {"kind": "ObservationReceipt", "evidence_level": "SIMULATED"})["verdict"] == "REJECT"
    assert tc.check_evidence_promotion(sim, "SIMULATED", None)["verdict"] == "ALLOW"


def test_T4_graph_edge_is_not_causality():
    assert tc.check_edge_promotion({"rel": "DERIVED_FROM", "promote_to": "CAUSES"}, None)["verdict"] == "ABSTAIN"
    assert tc.check_edge_promotion({"rel": "DERIVED_FROM"}, None)["verdict"] == "ALLOW"


def test_T5_custody_is_not_correctness(tmp_path):
    wrong = evolve([0, 0, 0, 1, 0, 0, 0], 30, 3)
    wrong[2][0] ^= 1                                              # deliberately wrong result
    p = tmp_path / "result.json"
    p.write_text(str(wrong))
    sha = hashlib.sha256(p.read_bytes()).hexdigest()
    root1, _ = fmo_root({"r": [("result.json", leaf("result.json", p.stat().st_size, sha))]})
    root2, _ = fmo_root({"r": [("result.json", leaf("result.json", p.stat().st_size, hashlib.sha256(p.read_bytes()).hexdigest()))]})
    custody_pass = root1 == root2
    correct = wrong == evolve([0, 0, 0, 1, 0, 0, 0], 30, 3)
    assert custody_pass and not correct
    assert tc.check_custody_vs_correctness(custody_pass, None)["verdict"] == "ABSTAIN"
    assert tc.check_custody_vs_correctness(custody_pass, correct)["verdict"] == "REJECT"


def test_T6_history_conditions_are_distinct_and_measured():
    hist = _glider_history()
    correct = life.kinematics(hist)
    rng = random.Random(0)
    past = hist[:-1]
    rng.shuffle(past)
    shuffled = life.kinematics(past + [hist[-1]])
    none = life.kinematics([hist[-1]])
    assert correct[0]["motion"] == "MOVING"
    assert none[0]["motion"] == "UNKNOWN"
    assert str(correct) != str(none)    # the difference is measured and recorded; shuffled is recorded, not assumed
    assert isinstance(shuffled, list)


def test_T7_observation_layer_loss_is_not_world_absence():
    import ale_py
    from src.envcfg import make_env
    gym.register_envs(ale_py)

    def grey_cols(o):
        return len(set(np.nonzero((o[20:195] == (142, 142, 142)).all(-1))[1]))

    raw = gym.make("ALE/SpaceInvaders-v5", obs_type="rgb", frameskip=1, repeat_action_probability=0.25)
    builtin = gym.make("ALE/SpaceInvaders-v5", obs_type="rgb", frameskip=4, repeat_action_probability=0.25)
    pooled = make_env()
    for e in (raw, builtin, pooled):
        e.reset(seed=1)
    raw_max = builtin_max = pooled_max = 0
    for t in range(300):
        a = 4 if (t // 30) % 2 == 0 else 5
        for _ in range(4):
            o, *_ = raw.step(a)
            raw_max = max(raw_max, grey_cols(o))                    # RawFrameSequence
        builtin_max = max(builtin_max, grey_cols(builtin.step(a)[0]))  # AggregatedObservation (sampled)
        pooled_max = max(pooled_max, grey_cols(pooled.step(a)[0]))     # AggregatedObservation (max-pooled)
    assert raw_max >= 2 and builtin_max <= 1 and pooled_max >= 2
    assert tc.CONTRACT["forbidden_promotions"][-1]["id"] == "T7"
