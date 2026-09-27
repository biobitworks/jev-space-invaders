"""0-Vita-1 type-safety checks. Pure functions over plain dicts; no private System-0 logic.

Each check returns a verdict dict: {"verdict": "ALLOW" | "REJECT" | "ABSTAIN", "rule": id, "reason": ...}.
"""
from __future__ import annotations

import json
from pathlib import Path

CONTRACT = json.loads((Path(__file__).resolve().parents[2] / "vita01" / "VITA01_TYPE_CONTRACT_V1.json").read_text())
RANK = CONTRACT["evidence_level_rank"]
FORBIDDEN_PACKET_FIELDS = set(CONTRACT["object_types"]["ContextPacket"]["forbidden_fields"])


def _v(verdict, rule, reason):
    return {"verdict": verdict, "rule": rule, "reason": reason}


def check_observation_promotion(obj: dict, new_status: str, receipt: dict | None) -> dict:
    """T2: a PREDICTED object may become OBSERVED only with an independent observation receipt."""
    if obj.get("observation_status") == "PREDICTED" and new_status == "OBSERVED":
        if not receipt or receipt.get("kind") != "ObservationReceipt":
            return _v("REJECT", "T2", "prediction cannot be marked observed without an ObservationReceipt")
        if receipt.get("source_id") == obj.get("id"):
            return _v("REJECT", "T2", "the observation receipt is the prediction itself")
    return _v("ALLOW", "T2", "no promotion or receipt present")


def check_evidence_promotion(obj: dict, target_level: str, receipt: dict | None) -> dict:
    """T3: evidence level may not increase without an observation receipt at the target level."""
    cur = obj.get("evidence_level", "SIMULATED")
    if RANK[target_level] > RANK[cur]:
        if not receipt or receipt.get("kind") != "ObservationReceipt" or receipt.get("evidence_level") != target_level:
            return _v("REJECT", "T3", f"{cur} -> {target_level} requires an ObservationReceipt at {target_level}")
    return _v("ALLOW", "T3", "no upgrade, or upgrade backed by a receipt at the target level")


def check_edge_promotion(edge: dict, intervention_ref: dict | None) -> dict:
    """T4: an FCG relation is not a causal edge. Without controlled-intervention evidence -> ABSTAIN."""
    if edge.get("rel") == "CAUSES" or edge.get("promote_to") == "CAUSES":
        if not intervention_ref or intervention_ref.get("kind") != "ControlledInterventionReceipt":
            return _v("ABSTAIN", "T4", "FCG_EDGE != CAUSAL_EDGE; no controlled-intervention evidence")
    return _v("ALLOW", "T4", "not a causal promotion")


def check_custody_vs_correctness(custody_pass: bool, correctness_check: bool | None) -> dict:
    """T5: custody establishes identity/inclusion; claim support needs a correctness check."""
    if custody_pass and correctness_check is None:
        return _v("ABSTAIN", "T5", "custody PASS alone does not establish correctness")
    if custody_pass and correctness_check is False:
        return _v("REJECT", "T5", "custody PASS, correctness FAILED")
    return _v("ALLOW", "T5", "custody and correctness both evaluated")


def check_identity_vs_meaning(source_a: str, source_b: str, context_a: dict, context_b: dict) -> dict:
    """T1: equal content ids do not imply equal interpretations."""
    same_id, same_ctx = source_a == source_b, context_a == context_b
    if same_id and not same_ctx:
        return _v("ALLOW", "T1", "identical source identity with distinct contexts: kept as separate ContextFCOs")
    return _v("ALLOW", "T1", f"same_id={same_id} same_context={same_ctx}")


def check_packet_leakage(packet: dict) -> dict:
    def keys(o):
        if isinstance(o, dict):
            for k, v in o.items():
                yield k
                yield from keys(v)
        elif isinstance(o, list):
            for v in o:
                yield from keys(v)
    bad = FORBIDDEN_PACKET_FIELDS & set(keys(packet))
    return _v("REJECT", "LEAKAGE", f"decision fields in packet: {sorted(bad)}") if bad else _v("ALLOW", "LEAKAGE", "no decision fields")
