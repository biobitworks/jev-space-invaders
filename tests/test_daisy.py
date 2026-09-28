import json

import jsonschema
import pytest

from experiments import e4b_ablation, e4c_graph
from src.daisy import deltag_candidate as dg
from src.daisy import eca_corpus as e
from src.daisy import openjev_behavior as ob
from src.kernels.eca import eca_step
from src.s01.protocol import make_packet

SCHEMA = lambda n: json.load(open(f"schemas/daisy/{n}.json"))  # noqa: E731


def test_all_256_truth_tables_match_kernel():
    for r in range(256):
        tt = e.truth_table(r)
        for j in range(8):
            l, c, rr = (j >> 2) & 1, (j >> 1) & 1, j & 1
            assert eca_step([l, c, rr], r, boundary="zero")[1] == tt[j]


def test_orbits_known():
    assert e.orbit(30) == [30, 86, 135, 149] and e.orbit(110) == [110, 124, 137, 193]


def test_deterministic_regeneration_and_hashing():
    a, b = e.action_rows(90, "rand1"), e.action_rows(90, "rand1")
    assert a == b
    assert e.row_hash((0, 1)) != e.row_hash((1, 0))


def test_trajectory_dedup_flags_repeats():
    rows = e.transition_rows(0, "rand1")        # rule 0 -> all-zero fixed point repeats
    assert any(r["duplicate_of_earlier_transition"] for r in rows)


def test_action_equivalence_merge():
    rows = e.trajectory(0, "single", 3)          # rule 0: empty hazard after t=0
    g = e.graph(0, rows, 0, 8, 2)
    assert g["layers"][2][8] == 3                # LR, RL, SS all reach x=8: merged with multiplicity 3


def test_split_has_no_family_leakage():
    seen = {}
    for r in range(256):
        for ic in e.ICS:
            s = e.split_of(r, ic)
            if ic != e.IC_HOLDOUT:
                seen.setdefault(min(e.orbit(r)), set()).add(s)
    assert all(len(v) == 1 for v in seen.values())
    assert all(e.split_of(r, e.IC_HOLDOUT) == "test_ic_holdout" for r in range(256))


def test_public_anticube_serialises_and_rows_validate_1p():
    rows = e.action_rows(4, "single")
    json.dumps(rows[0]["public_anticube"])
    for r in rows:
        jsonschema.validate(r, SCHEMA("daisy_1p_row_v1"))


def test_1p_2p_schema_separation():
    r = e.action_rows(4, "single")[0]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({**r, "opponent_action": "LEFT"}, SCHEMA("daisy_1p_row_v1"))
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(r, SCHEMA("daisy_2p_row_v1"))


def test_model_free_rows_never_carry_deltag():
    for r in e.action_rows(30, "single"):
        assert r["delta_G_star"] == "NOT_COMPUTED" and r["H_norm"] == "NOT_COMPUTED" and r["provider"] == "NOT_APPLICABLE"


def test_candidate_deltag_versioned_and_not_computed_without_probs():
    u = {"LEFT": 1, "STAY": 0, "RIGHT": 0}
    assert dg.compute("NOT_AVAILABLE", u, "STAY")["delta_G_star"] == "NOT_COMPUTED"
    out = dg.compute({"LEFT": 0.1, "STAY": 0.8, "RIGHT": 0.1}, u, "STAY")
    assert out["delta_g_definition_id"].startswith("PUBLIC_CANDIDATE_DELTAGSTAR_V1:sha256:")
    assert isinstance(out["delta_G_star"], float)


def test_openjev_corpus_isolated_and_joined_by_state_id():
    rows = e.action_rows(4, "single")

    class Fake:
        requested_model = "fake"

        def decide_body(self, body, prev):
            from src.deciders import Decision
            assert b"recommended" not in body
            return Decision(action="STAY", proposed_action="STAY", probabilities={"LEFT": 0.2, "STAY": 0.6, "RIGHT": 0.2},
                            served_model="fake-openjev", model_call=True)
    split = rows[0]["split"]
    beh = ob.behavior_rows(rows, Fake(), split=split)
    assert beh and all(b["corpus_id"] == "OPENJEV_DAISY_BEHAVIOR_CORPUS_V1" and "optimal_action_set" not in b for b in beh)
    assert all("provider" not in r or r["provider"] == "NOT_APPLICABLE" for r in rows)
    cmp_ = ob.comparison_rows(rows, beh)
    assert cmp_ and {c["state_id"] for c in cmp_} <= {r["state_id"] for r in rows}


def test_no_recommended_action_leakage_in_arms():
    r = e.action_rows(4, "single")[0]
    for arm in ob.ARMS:
        ctx = e.arm_context(r, arm, other=r, seed=1)
        make_packet("eca", [r["state_id"]], ctx, list(e.ACTIONS), ob.QUESTION, {"name": "public", "version": "1"}, 0.0)


def test_e4b_e4c_schema_separation():
    assert e4b_ablation.IN_ID != e4c_graph.IN_ID and e4b_ablation.EXP != e4c_graph.EXP
    assert set(e4c_graph.ACTIONS) == {"NOOP", "FIRE", "RIGHT", "LEFT", "RIGHTFIRE", "LEFTFIRE"}
    assert set(e.ACTIONS) == {"LEFT", "STAY", "RIGHT"}
