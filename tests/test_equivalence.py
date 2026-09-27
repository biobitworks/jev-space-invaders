import pytest

from src.vita01.equivalence import ContractError, classify, equivalent, freeze_rule, raw_value

TOL = {"rule_id": "temp-eq", "version": "1", "quantity": "temperature", "units": "K", "mode": "tolerance",
       "tolerance": {"abs": 0.05, "k_sigma": 2.0}, "uncertainty_method": "absolute_1sigma", "boundary": "closed"}
BIN = {"rule_id": "temp-bin", "version": "1", "quantity": "temperature", "units": "K", "mode": "bin",
       "bin": {"origin": 0, "width": 0.5}, "uncertainty_method": "none_declared_exact", "boundary": "left_closed"}


def test_raw_identity_is_exact_bytes():
    a, b = raw_value("1.0", "K"), raw_value("1.00", "K")
    assert a["raw_id"] != b["raw_id"]                       # different raw bytes never share a hash
    assert raw_value("1.0", "K")["raw_id"] == a["raw_id"]   # same raw bytes, same identity


def test_equivalence_needs_frozen_complete_rule():
    for f in ("version", "units", "uncertainty_method", "boundary"):
        with pytest.raises(ContractError):
            freeze_rule({k: v for k, v in TOL.items() if k != f})
    r = freeze_rule(TOL)
    tampered = dict(r, tolerance={"abs": 9})
    with pytest.raises(ContractError):
        equivalent(raw_value("1.0", "K"), raw_value("1.00", "K"), tampered)


def test_contextual_equivalence_and_units():
    r = freeze_rule(TOL)
    j = equivalent(raw_value("1.0", "K", "0.01"), raw_value("1.00", "K", "0.01"), r)
    assert j["equivalent"] and not j["same_raw_identity"]
    with pytest.raises(ContractError):
        equivalent(raw_value("1.0", "K"), raw_value("1.0", "degC"), r)


def test_boundary_semantics_matter():
    closed = freeze_rule(dict(TOL, tolerance={"abs": 0.5}, uncertainty_method="none_declared_exact"))
    opened = freeze_rule(dict(TOL, tolerance={"abs": 0.5}, uncertainty_method="none_declared_exact", boundary="open"))
    a, b = raw_value("1.0", "K"), raw_value("1.5", "K")
    assert equivalent(a, b, closed)["equivalent"] and not equivalent(a, b, opened)["equivalent"]
    lc, rc = freeze_rule(BIN), freeze_rule(dict(BIN, boundary="right_closed"))
    assert classify(raw_value("1.0", "K"), lc)["bin_index"] == 2
    assert classify(raw_value("1.0", "K"), rc)["bin_index"] == 1


def test_shared_class_identity_and_immutable_successors():
    r1 = freeze_rule(BIN)
    c1 = classify(raw_value("1.10", "K"), r1)
    c2 = classify(raw_value("1.40", "K"), r1)
    assert c1["class_id"] == c2["class_id"] and c1["raw_id"] != c2["raw_id"]
    r2 = freeze_rule(dict(BIN, version="2", bin={"origin": 0, "width": 0.25}))
    succ = classify(raw_value("1.10", "K"), r2, predecessor=c1)
    assert succ["predecessor_ref"] == c1["classification_id"] and succ["class_id"] != c1["class_id"]
    assert classify(raw_value("1.10", "K"), r1) == c1       # history reproducible, never rewritten
