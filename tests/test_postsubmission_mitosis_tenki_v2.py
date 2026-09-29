from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_secret_patterns_detect_synthetic_fixtures():
    mod = load_module("claims_v2", "tools/verify_mitosis_tenki_claims_v2.py")
    fixtures = {
        "MITOSIS_KEY": "mi_SYNTHETICKEY1234567890",
        "TENKI_KEY": "tk_SYNTHETICKEY1234567890",
        "BEARER": "Bearer SYNTHETIC-TOKEN-1234567890",
        "AWS_ACCESS_KEY": "ASIA1234567890ABCDEF",
        "PRIVATE_KEY": "-----BEGIN PRIVATE KEY-----",
    }
    for expected, text in fixtures.items():
        assert expected in mod.secret_scan_text(text)


def test_secret_patterns_do_not_flag_status_only():
    mod = load_module("claims_v2_safe", "tools/verify_mitosis_tenki_claims_v2.py")
    assert mod.secret_scan_text("MI_API_KEY=SET TENKI_API_KEY=BLOCKED") == []


def test_outcome_score_predicate_is_deterministic():
    mod = load_module("outcome_v1", "scripts/determine_game_outcome_v1.py")
    assert mod.winner_from_scores(10.0, 5.0) == "LEFT"
    assert mod.winner_from_scores(5.0, 10.0) == "RIGHT"
    assert mod.winner_from_scores(7.0, 7.0) == "TIE"


def test_frozen_outcome_predicate_never_equates_positive_score_with_literal_win():
    doc = json.loads((ROOT / "governance/postsubmission/GAME_OUTCOME_PREDICATE_V1.json").read_text())
    assert doc["rules"]["one_player_evaluation"]["literal_game_win_claim"] is False
    assert doc["rules"]["literal_game_completion"]["status"] == "NOT_DEFINED"
    assert "positive score" in doc["rules"]["literal_game_completion"]["forbidden_proxies"]


def test_v2_contract_requires_replay_and_outcome_review_targets():
    doc = json.loads((ROOT / "governance/postsubmission/MITOSIS_TENKI_E2E_REVIEW_CONTRACT_V2.json").read_text())
    targets = set(doc["review_targets"])
    assert "scripts/verify_environment_replay_v1.py" in targets
    assert "scripts/determine_game_outcome_v1.py" in targets
    assert "scripts/verify_final_playthrough_custody_v2.py" in targets
    assert "scripts/verify_competition_lineage.py" in targets
