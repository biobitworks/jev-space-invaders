"""VITA01 continuous equivalence: exact raw identity, rule-governed contextual equivalence.

Raw identity is the hash of the exact observed string. Equivalence is never inferred from
hashes; it comes only from a frozen, versioned rule with units, an uncertainty method and
boundary semantics. Classifications are immutable; new evidence or a new rule version
creates a successor that points to its predecessor.
"""
from __future__ import annotations

import math
from decimal import Decimal

from src.s01.canon import content_id

REQUIRED_RULE_FIELDS = ("rule_id", "version", "quantity", "units", "mode", "uncertainty_method", "boundary")
UNCERTAINTY = {"none_declared_exact", "absolute_1sigma", "relative_1sigma"}
BOUNDARY = {"tolerance": {"closed", "open"}, "bin": {"left_closed", "right_closed"}}


class ContractError(ValueError):
    pass


def raw_value(raw: str, units: str, uncertainty: str | None = None) -> dict:
    if not isinstance(raw, str):
        raise ContractError("raw value must be the exact observed string")
    if not units:
        raise ContractError("UNITS_REQUIRED")
    v = {"kind": "RawValueFCO", "raw": raw, "units": units}
    if uncertainty is not None:
        v["uncertainty"] = uncertainty
    v["raw_id"] = content_id({k: v[k] for k in ("kind", "raw", "units") if k in v} | ({"uncertainty": uncertainty} if uncertainty else {}))
    return v


def freeze_rule(rule: dict) -> dict:
    missing = [f for f in REQUIRED_RULE_FIELDS if not rule.get(f)]
    if missing:
        raise ContractError(f"rule missing {missing}")
    if rule["uncertainty_method"] not in UNCERTAINTY:
        raise ContractError("UNCERTAINTY_METHOD_REQUIRED")
    if rule["boundary"] not in BOUNDARY.get(rule["mode"], set()):
        raise ContractError("BOUNDARY_SEMANTICS_REQUIRED for this mode")
    if rule["mode"] == "bin" and not ("origin" in rule.get("bin", {}) and rule["bin"].get("width")):
        raise ContractError("bin mode needs origin and width")
    r = {"kind": "EquivalenceRuleFCO", **rule}
    r["rule_hash"] = content_id(r)
    return r


def _check(rule: dict, *vals: dict) -> None:
    if "rule_hash" not in rule or content_id({k: v for k, v in rule.items() if k != "rule_hash"}) != rule["rule_hash"]:
        raise ContractError("EQUIVALENCE_REQUIRES_FROZEN_RULE")
    for v in vals:
        if v["units"] != rule["units"]:
            raise ContractError(f"units {v['units']} != rule units {rule['units']}")


def _sigma(v: dict, rule: dict) -> float:
    if rule["uncertainty_method"] == "none_declared_exact":
        return 0.0
    u = float(v.get("uncertainty") or 0)
    return u * abs(float(Decimal(v["raw"]))) if rule["uncertainty_method"] == "relative_1sigma" else u


def equivalent(a: dict, b: dict, rule: dict) -> dict:
    _check(rule, a, b)
    x, y = float(Decimal(a["raw"])), float(Decimal(b["raw"]))
    t = rule.get("tolerance", {})
    tol = t.get("abs", 0.0) + t.get("rel", 0.0) * max(abs(x), abs(y)) + t.get("k_sigma", 0.0) * math.hypot(_sigma(a, rule), _sigma(b, rule))
    d = abs(x - y)
    eq = d <= tol if rule["boundary"] == "closed" else d < tol
    return {"kind": "EquivalenceJudgementFCO", "a": a["raw_id"], "b": b["raw_id"], "rule_hash": rule["rule_hash"],
            "same_raw_identity": a["raw_id"] == b["raw_id"], "equivalent": eq, "distance": d, "tolerance": tol}


def classify(v: dict, rule: dict, predecessor: dict | None = None) -> dict:
    _check(rule, v)
    if rule["mode"] != "bin":
        raise ContractError("classify needs a bin-mode rule")
    x = Decimal(v["raw"])
    o, w = Decimal(str(rule["bin"]["origin"])), Decimal(str(rule["bin"]["width"]))
    q = (x - o) / w
    idx = math.floor(q) if rule["boundary"] == "left_closed" else math.ceil(q) - 1
    cls = {"kind": "EquivalenceClassFCO", "rule_hash": rule["rule_hash"], "bin_index": idx}
    out = {"kind": "ClassificationFCO", "raw_id": v["raw_id"], "class_id": content_id(cls), "rule_hash": rule["rule_hash"],
           "bin_index": idx, "predecessor_ref": predecessor["classification_id"] if predecessor else None}
    out["classification_id"] = content_id(out)
    return out
