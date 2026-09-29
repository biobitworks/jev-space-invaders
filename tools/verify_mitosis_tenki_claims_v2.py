#!/usr/bin/env python3
"""V2 Mitosis/Tenki claim-integrity validator.

This is a successor to the PR #3 validator. It fixes the secret regexes,
requires every contract-declared review target, treats malformed evidence as a
blocker, requires exact Mitosis universal-ID retrieval, and never equates Tenki
code review with Tenki clean-room execution.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "governance/postsubmission/MITOSIS_TENKI_E2E_REVIEW_CONTRACT_V2.json"

EXPECTED_MMR = "e55a47a7f16064477c4f101a38a849391c2fbc9f6557c5244daf0406b36dbd74"
EXPECTED_SUBMITTED_COMMIT = "4c943a92e84d0fb2cd3d01e4fdf15a10991eda71"

SECRET_PATTERNS = [
    ("MITOSIS_KEY", re.compile(r"\bmi_[A-Za-z0-9_-]{12,}")),
    ("TENKI_KEY", re.compile(r"\btk_[A-Za-z0-9_-]{12,}")),
    ("BEARER", re.compile(r"Bearer\s+[A-Za-z0-9._~+/-]{12,}", re.I)),
    ("AWS_ACCESS_KEY", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("PRIVATE_KEY", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")),
]

JSON_EVIDENCE = {
    "mitosis_post": "evidence/competition/post_submission/mitosis/MITOSIS_POST_SUBMISSION_VERIFICATION_FCO.json",
    "tenki_post": "evidence/competition/post_submission/tenki/TENKI_SUBMITTED_REPLAY_VERIFICATION_FCO.json",
    "tenki_correction": "evidence/competition/post_submission/tenki/TENKI_SUBMITTED_REPLAY_VERIFICATION_CORRECTION_FCO_V2.json",
    "playthrough": "evidence/competition/final_execution/frames/PLAYTHROUGH_MMR_VERIFICATION_RECEIPT_V2.json",
}


def load_json(path: Path, blockers: list[str], label: str) -> dict:
    if not path.exists():
        blockers.append(f"MISSING_FILE:{path.relative_to(ROOT)}")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        blockers.append(f"MALFORMED_JSON:{label}:{type(exc).__name__}")
        return {}


def secret_scan_text(text: str) -> list[str]:
    return [name for name, pattern in SECRET_PATTERNS if pattern.search(text)]


def exact_mitosis_post_ok(m: dict) -> bool:
    uid = m.get("new_universal_id")
    return all([
        m.get("mitosis_auth") == "PASS",
        m.get("remember_status") == "PASS",
        m.get("mitosis_query_back") == "PASS",
        m.get("mitosis_exact_id_match") == "YES",
        m.get("mitosis_get_new_memory") == "PASS",
        m.get("mitosis_persistence_retrieval") == "PASS",
        bool(uid),
        m.get("query_top_universal_id") == uid,
    ])


def tenki_clean_room_supported(t: dict) -> bool:
    return all([
        t.get("tenki_sandbox_create") == "PASS",
        t.get("tenki_source_pin") == "PASS",
        t.get("playthrough_verify") == "PASS",
        int(t.get("frames_checked", 0)) == 240,
        t.get("recomputed_mmr_root") == EXPECTED_MMR,
    ])


def tenki_environment_supported(t: dict) -> bool:
    return all([
        tenki_clean_room_supported(t),
        t.get("environment_replay") == "PASS",
        t.get("replay_from_start") == "PASS",
        t.get("step_hash_equality") == "PASS",
        t.get("final_mmr_equality") == "PASS",
    ])


def load_bearing_supported() -> tuple[bool, dict]:
    """Require exact writeback identity + explicit Vithia consumption + DecisionFCO edge."""
    base = ROOT / "evidence/competition/post_submission/e2e"
    anchor_p = base / "MITOSIS_VERIFICATION_ANCHOR_FCO.json"
    context_p = base / "VITHIA_VERIFIED_CONTEXT_FCO.json"
    decision_p = base / "DECISION_FCO.json"
    if not (anchor_p.exists() and context_p.exists() and decision_p.exists()):
        return False, {"state": "NOT_ESTABLISHED", "reason": "required successor FCOs absent"}
    try:
        anchor = json.loads(anchor_p.read_text(encoding="utf-8"))
        context = json.loads(context_p.read_text(encoding="utf-8"))
        decision = json.loads(decision_p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return False, {"state": "NOT_ESTABLISHED", "reason": f"malformed successor evidence:{type(exc).__name__}"}

    uid = anchor.get("verification_universal_id")
    exact = all([
        bool(uid),
        anchor.get("mitosis_writeback") == "PASS",
        anchor.get("query_back") == "PASS",
        anchor.get("exact_id_match") == "YES",
        anchor.get("get_by_id") == "PASS",
    ])
    consumed = all([
        context.get("verification_memory_consumed") == "YES",
        context.get("mitosis_verification_universal_id") == uid,
        bool(context.get("context_root")),
        decision.get("input_context_root") == context.get("context_root"),
        decision.get("consumed_verification_universal_id") == uid,
    ])
    return exact and consumed, {
        "state": "PASS_BOUNDED" if exact and consumed else "NOT_ESTABLISHED",
        "verification_universal_id": uid,
        "exact_retrieval": exact,
        "downstream_consumption": consumed,
    }


def main() -> int:
    blockers: list[str] = []
    findings: list[dict] = []

    contract = load_json(CONTRACT, blockers, "contract")
    targets = contract.get("review_targets", [])
    for rel in targets:
        path = ROOT / rel
        if not path.exists():
            blockers.append(f"MISSING_CONTRACT_REVIEW_TARGET:{rel}")
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            blockers.append(f"UNREADABLE_REVIEW_TARGET:{rel}:{type(exc).__name__}")
            continue
        for pattern_name in secret_scan_text(text):
            blockers.append(f"POSSIBLE_SECRET_IN_PUBLIC_FILE:{pattern_name}:{rel}")

    docs = {
        label: load_json(ROOT / rel, blockers, label)
        for label, rel in JSON_EVIDENCE.items()
    }

    m = docs["mitosis_post"]
    mitosis_ok = exact_mitosis_post_ok(m)
    findings.append({
        "check": "MITOSIS_POST_EXACT_PERSISTENCE_RETRIEVAL",
        "status": "PASS" if mitosis_ok else "FAIL",
        "new_universal_id": m.get("new_universal_id"),
        "query_top_universal_id": m.get("query_top_universal_id"),
    })
    if not mitosis_ok:
        blockers.append("MITOSIS_POST_EXACT_PERSISTENCE_RETRIEVAL_NOT_PROVEN")

    if m.get("submitted_source_commit") != EXPECTED_SUBMITTED_COMMIT:
        blockers.append("MITOSIS_POST_WRONG_SUBMITTED_SOURCE_COMMIT")
    if m.get("playthrough_mmr_root") != EXPECTED_MMR:
        blockers.append("MITOSIS_POST_WRONG_PLAYTHROUGH_ROOT")

    p = docs["playthrough"]
    local_playthrough_ok = all([
        p.get("PLAYTHROUGH_VERIFY") == "PASS",
        int(p.get("frames_checked", 0)) == 240,
        p.get("recomputed_mmr_root") == EXPECTED_MMR,
        p.get("recorded_mmr_root") == EXPECTED_MMR,
    ])
    findings.append({
        "check": "LOCAL_PLAYTHROUGH_CUSTODY_MMR",
        "status": "PASS" if local_playthrough_ok else "FAIL",
        "frames_checked": p.get("frames_checked"),
        "mmr_root": p.get("recomputed_mmr_root"),
    })
    if not local_playthrough_ok:
        blockers.append("LOCAL_PLAYTHROUGH_CUSTODY_MMR_FAILED")

    t = docs["tenki_post"]
    c = docs["tenki_correction"]
    clean_supported = tenki_clean_room_supported(t)
    env_supported = tenki_environment_supported(t)

    historical_overclaim = (
        t.get("artifact_reconstruction") == "PASS"
        and not clean_supported
    )
    correction_valid = all([
        c.get("schema") == "TENKI_SUBMITTED_REPLAY_VERIFICATION_CORRECTION_FCO_V2",
        c.get("correction_of") == JSON_EVIDENCE["tenki_post"],
        c.get("tenki_clean_room_artifact_reconstruction") == "NOT_ESTABLISHED",
        c.get("tenki_environment_replay") == "NOT_ESTABLISHED",
        c.get("mutation_of_predecessor") is False,
    ])
    findings.append({
        "check": "TENKI_HISTORICAL_CLAIM_CORRECTION",
        "historical_overclaim_detected": historical_overclaim,
        "corrective_successor": "PASS" if correction_valid else "FAIL",
    })
    if historical_overclaim and not correction_valid:
        blockers.append("UNCORRECTED_TENKI_ARTIFACT_RECONSTRUCTION_OVERCLAIM")

    findings.append({
        "check": "TENKI_CLEAN_ROOM_ARTIFACT_RECONSTRUCTION",
        "status": "PASS" if clean_supported else "NOT_ESTABLISHED",
        "sandbox_create": t.get("tenki_sandbox_create"),
        "source_pin": t.get("tenki_source_pin"),
        "playthrough_verify": t.get("playthrough_verify"),
    })
    findings.append({
        "check": "TENKI_ENVIRONMENT_REPLAY",
        "status": "PASS" if env_supported else "NOT_ESTABLISHED",
    })

    load_bearing, load_detail = load_bearing_supported()
    findings.append({
        "check": "PORTABLE_AGENT_MEMORY_LOAD_BEARING",
        **load_detail,
    })

    # No current PASS claim is allowed unless all causal prerequisites are present.
    claimed_states = [
        m.get("portable_agent_memory_load_bearing"),
        c.get("portable_agent_memory_load_bearing"),
    ]
    if any(x in ("PASS", "PASS_BOUNDED") for x in claimed_states) and not load_bearing:
        blockers.append("CLAIM_OVERREACH:PORTABLE_AGENT_MEMORY_LOAD_BEARING")

    report = {
        "schema": "MITOSIS_TENKI_E2E_CLAIM_REVIEW_V2",
        "submitted_source_commit": EXPECTED_SUBMITTED_COMMIT,
        "expected_playthrough_mmr_root": EXPECTED_MMR,
        "contract_review_targets_checked": len(targets),
        "findings": findings,
        "blockers": sorted(set(blockers)),
        "review_verdict": "PASS" if not blockers else "BLOCKED",
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not blockers else 2


if __name__ == "__main__":
    raise SystemExit(main())
