#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FILES = {
    "mitosis": ROOT / "evidence/competition/final_execution/MITOSIS_FINAL_EXECUTION_RECEIPT.json",
    "tenki_final": ROOT / "evidence/competition/final_execution/TENKI_FINAL_EXECUTION_RECEIPT.json",
    "sponsor_keys": ROOT / "evidence/competition/final_execution/SPONSOR_KEY_VERIFICATION_RECEIPT.json",
    "tenki_post": ROOT / "evidence/competition/post_submission/tenki/TENKI_SUBMITTED_REPLAY_VERIFICATION_FCO.json",
    "playthrough": ROOT / "evidence/competition/final_execution/frames/PLAYTHROUGH_MMR_VERIFICATION_RECEIPT_V2.json",
}

EXPECTED_MMR = "e55a47a7f16064477c4f101a38a849391c2fbc9f6557c5244daf0406b36dbd74"
EXPECTED_SUBMITTED_COMMIT = "4c943a92e84d0fb2cd3d01e4fdf15a10991eda71"

SECRET_PATTERNS = [
    re.compile(r"\bmi_[A-Za-z0-9_-]{12,}"),
    re.compile(r"\btk_[A-Za-z0-9_-]{12,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9._~+/-]{12,}", re.I),
    re.compile(r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----"),
]

# Guard against the patterns silently becoming no-ops again.
for _sample in ("m" + "i_abcdefghij12", "t" + "k_abcdefghij12", "Bear" + "er eyJhbGciOiJIUzI1NiJ9abc", "-----BEGIN " + "PRIVATE KEY-----"):
    assert any(_p.search(_sample) for _p in SECRET_PATTERNS), f"secret pattern self-test failed: {_sample}"

EXTRA_REVIEW_TARGETS = [
    ROOT / "scripts/verify_final_playthrough_custody_v2.py",
    ROOT / "scripts/verify_competition_lineage.py",
]
CORRECTION_FCO = ROOT / "evidence/post_submission/e2e/TENKI_CLAIM_CORRECTION_FCO.json"

def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))

def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def superseded_by_correction(target: Path) -> bool:
    """A correction only counts if it cites the exact bytes of the overstated file and does not itself claim PASS."""
    if not CORRECTION_FCO.exists():
        return False
    c = load(CORRECTION_FCO)
    return (
        c.get("schema") == "TENKI_CLAIM_CORRECTION_FCO_V1"
        and c.get("supersedes_sha256") == sha256_file(target)
        and c.get("corrected_artifact_reconstruction") == "NOT_ESTABLISHED"
        and c.get("corrected_environment_replay") in ("NOT_ESTABLISHED", "NOT_IMPLEMENTED")
    )

def main() -> int:
    findings = []
    blockers = []
    docs = {}
    for name, path in FILES.items():
        if not path.exists():
            blockers.append(f"MISSING_FILE:{path.relative_to(ROOT)}")
            continue
        docs[name] = load(path)

    for extra in EXTRA_REVIEW_TARGETS:
        if not extra.exists():
            blockers.append(f"MISSING_FILE:{extra.relative_to(ROOT)}")

    # Secret boundary: scan only public review targets.
    for path in list(FILES.values()) + EXTRA_REVIEW_TARGETS:
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pat in SECRET_PATTERNS:
            if pat.search(text):
                blockers.append(f"POSSIBLE_SECRET_IN_PUBLIC_FILE:{path.relative_to(ROOT)}")

    m = docs.get("mitosis", {})
    historical_mitosis_pass = (
        m.get("MITOSIS_USED") is True
        and m.get("state") == "EXECUTED_REMEMBER_AND_RETRIEVE"
        and bool(m.get("remember_universal_id"))
        and m.get("retrieval_top_universal_id") == m.get("remember_universal_id")
    )
    findings.append({
        "check": "HISTORICAL_MITOSIS_EXACT_RETRIEVAL",
        "status": "PASS" if historical_mitosis_pass else "FAIL",
        "universal_id": m.get("remember_universal_id"),
    })
    if not historical_mitosis_pass:
        blockers.append("MITOSIS_HISTORICAL_EXACT_RETRIEVAL_NOT_PROVEN")

    tf = docs.get("tenki_final", {})
    findings.append({
        "check": "TENKI_FINAL_EXECUTION_STATE",
        "status": tf.get("state", "UNKNOWN"),
        "tenki_used": tf.get("TENKI_USED"),
    })

    tp = docs.get("tenki_post", {})
    submitted_commit_match = tp.get("submitted_source_commit") == EXPECTED_SUBMITTED_COMMIT
    findings.append({
        "check": "TENKI_POST_SUBMITTED_SOURCE_PIN_METADATA",
        "status": "PASS" if submitted_commit_match else "FAIL",
        "recorded": tp.get("submitted_source_commit"),
    })
    if not submitted_commit_match:
        blockers.append("TENKI_POST_WRONG_SUBMITTED_SOURCE_COMMIT")

    sandbox_ok = tp.get("tenki_sandbox_create") == "PASS"
    source_pin_ok = tp.get("tenki_source_pin") == "PASS"
    playthrough_ok = tp.get("playthrough_verify") == "PASS"
    tenki_artifact_claimed = tp.get("artifact_reconstruction") == "PASS"
    tenki_artifact_supported = sandbox_ok and source_pin_ok and playthrough_ok

    findings.append({
        "check": "TENKI_CLEAN_ROOM_ARTIFACT_RECONSTRUCTION",
        "claimed": tp.get("artifact_reconstruction"),
        "supported": "PASS" if tenki_artifact_supported else "NOT_ESTABLISHED",
        "sandbox_create": tp.get("tenki_sandbox_create"),
        "source_pin": tp.get("tenki_source_pin"),
        "playthrough_verify": tp.get("playthrough_verify"),
    })
    if tenki_artifact_claimed and not tenki_artifact_supported:
        if superseded_by_correction(FILES["tenki_post"]):
            findings.append({"check": "TENKI_POST_OVERREACH", "status": "SUPERSEDED_BY_CORRECTION_FCO",
                             "correction": str(CORRECTION_FCO.relative_to(ROOT))})
        else:
            blockers.append("CLAIM_OVERREACH:TENKI_ARTIFACT_RECONSTRUCTION_PASS_WITHOUT_CLEAN_ROOM_EXECUTION")

    env_replay_supported = (
        tp.get("environment_replay") == "PASS"
        and tp.get("replay_from_start") == "PASS"
        and tp.get("step_hash_equality") == "PASS"
        and tp.get("final_mmr_equality") == "PASS"
    )
    findings.append({
        "check": "TENKI_ENVIRONMENT_REPLAY",
        "status": "PASS" if env_replay_supported else "NOT_ESTABLISHED",
    })

    pv = docs.get("playthrough", {})
    local_playthrough_ok = (
        pv.get("PLAYTHROUGH_VERIFY") == "PASS"
        and pv.get("frames_checked") == 240
        and pv.get("recomputed_mmr_root") == EXPECTED_MMR
        and pv.get("recorded_mmr_root") == EXPECTED_MMR
    )
    findings.append({
        "check": "LOCAL_PLAYTHROUGH_CUSTODY_MMR",
        "status": "PASS" if local_playthrough_ok else "FAIL",
        "frames_checked": pv.get("frames_checked"),
        "mmr_root": pv.get("recomputed_mmr_root"),
    })
    if not local_playthrough_ok:
        blockers.append("LOCAL_PLAYTHROUGH_CUSTODY_MMR_FAILED")

    sk = docs.get("sponsor_keys", {})
    providers = sk.get("providers", {})
    current_mitosis = providers.get("mitosis", {})
    current_tenki = providers.get("tenki", {})
    findings.append({
        "check": "LATEST_KEY_PROBE",
        "mitosis_auth": current_mitosis.get("MITOSIS_AUTH"),
        "tenki_auth": current_tenki.get("TENKI_AUTH"),
        "portable_agent_memory_load_bearing": sk.get("PORTABLE_AGENT_MEMORY_LOAD_BEARING"),
    })

    portable_supported = (
        tenki_artifact_supported
        and current_mitosis.get("MITOSIS_WRITE") == "PASS"
        and current_mitosis.get("MITOSIS_QUERY") == "PASS"
        and current_mitosis.get("MITOSIS_EXACT_ID_MATCH") == "YES"
        and sk.get("load_bearing_consumption", {}).get("consumed_in_decision") is True
    )
    if sk.get("PORTABLE_AGENT_MEMORY_LOAD_BEARING") in ("PASS", "PASS_BOUNDED") and not portable_supported:
        blockers.append("CLAIM_OVERREACH:PORTABLE_AGENT_MEMORY_LOAD_BEARING")

    report = {
        "schema": "MITOSIS_TENKI_E2E_CLAIM_REVIEW_V1",
        "submitted_source_commit": EXPECTED_SUBMITTED_COMMIT,
        "expected_playthrough_mmr_root": EXPECTED_MMR,
        "findings": findings,
        "blockers": blockers,
        "review_verdict": "PASS" if not blockers else "BLOCKED",
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not blockers else 2

if __name__ == "__main__":
    raise SystemExit(main())
