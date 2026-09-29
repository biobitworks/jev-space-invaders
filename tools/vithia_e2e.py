#!/usr/bin/env python3
"""Vithia -> Mitosis -> checkpoint -> Tenki -> Mitosis -> Vithia -> decider -> outcome, stage by stage.
Each stage writes immutable canonical FCOs and prints machine-readable KEY=VALUE lines."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vithia_e2e_lib as L  # noqa: E402

ROOT, E2E = L.ROOT, L.E2E_DIR
SUBMITTED = "4c943a92e84d0fb2cd3d01e4fdf15a10991eda71"
EXPECTED_MMR = "e55a47a7f16064477c4f101a38a849391c2fbc9f6557c5244daf0406b36dbd74"
ENTRY_ID = "b968c199-5d7e-4228-b8fe-b0003b7ab94f"
OFFICE = "b236ff3a-8250-4ac5-bda2-4fc35c43d35f"
HIST_UID = "agent:memories:47b923e2e5bf18083bbc05c3"
PREV_UID = "agent:memories:e0dc415cff19bd7244ebf8ba"
PR3 = "https://github.com/biobitworks/jev-space-invaders/pull/3"
ENV_FILE = ROOT / "vithia-space-sponsors.env"
FINAL = "evidence/competition/final_execution"


def out(**kv):
    for k, v in kv.items():
        print(f"{k}={v}")


def git_show_sha(commit: str, path: str) -> str:
    return L.sha(subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=ROOT))


def file_sha(rel: str) -> str:
    return L.sha((ROOT / rel).read_bytes())


def session_id() -> str:
    seed = E2E / "SEED_CHECKPOINT_FCO.json"
    return json.loads(seed.read_bytes())["session_id"] if seed.exists() else None


def stage_correction():
    hist = "evidence/competition/post_submission/tenki/TENKI_SUBMITTED_REPLAY_VERIFICATION_FCO.json"
    d = json.loads((ROOT / hist).read_text())
    h = L.write_fco(E2E / "TENKI_CLAIM_CORRECTION_FCO.json", {
        "schema": "TENKI_CLAIM_CORRECTION_FCO_V1", "supersedes_path": hist, "supersedes_sha256": file_sha(hist),
        "reason": ("Superseded file recorded artifact_reconstruction=PASS and tenki_auth=PASS while "
                   f"tenki_sandbox_create={d.get('tenki_sandbox_create')}, tenki_source_pin={d.get('tenki_source_pin')}, "
                   f"playthrough_verify={d.get('playthrough_verify')}. Credential presence and local file existence "
                   "are not Tenki authentication or clean-room reconstruction. The historical file is preserved unmodified."),
        "corrected_artifact_reconstruction": "NOT_ESTABLISHED", "corrected_environment_replay": "NOT_ESTABLISHED",
        "created_utc": L.utc()})
    out(TENKI_CLAIM_CORRECTION_FCO_SHA256=h)


def stage_seed():
    sid = "VITHIA-E2E-" + L.utc().replace("-", "").replace(":", "")
    replay = "evidence/post_submission/e2e/LOCAL_ENVIRONMENT_REPLAY_RECEIPT.json"
    objs = []
    for p in (f"{FINAL}/PLAYTHROUGH_FCO.json", f"{FINAL}/FINAL_1P_RUN_PREREG.json",
              f"{FINAL}/frames/FRAME_BREAKPOINT_LEAVES.jsonl", f"{FINAL}/frames/PLAYTHROUGH_MMR_CONSTRUCTION_RECEIPT.json",
              f"{FINAL}/frames/PLAYTHROUGH_MMR_VERIFICATION_RECEIPT_V2.json", f"{FINAL}/FRAME_CUSTODY_PUBLIC_KEY.pem",
              "governance/lineage/UFA_JEV_COMP_MMR_LEDGER.json"):
        a, b = git_show_sha(SUBMITTED, p), file_sha(p)
        if a != b:
            raise SystemExit(f"OBJECT_HASH_MISMATCH {p}")
        objs.append({"path": p, "sha256": a, "pinned_at": SUBMITTED})
    objs.append({"path": f"{FINAL}/frames/frame_NNNN.occurrence.json", "sha256": "SEE_FRAME_BREAKPOINT_LEAVES",
                 "pinned_at": SUBMITTED, "note": "240 frames; ordered roots pinned via FRAME_BREAKPOINT_LEAVES.jsonl"})
    tip = L.comp_ledger_tip()
    h = L.write_fco(E2E / "SEED_CHECKPOINT_FCO.json", {
        "schema": "SeedCheckpointFCO_V1", "session_id": sid, "submitted_source_commit": SUBMITTED,
        "submitted_playthrough_mmr_root": EXPECTED_MMR, "local_replay_receipt_hash": file_sha(replay),
        "parent_fcg_root": tip["mmr_root"], "parent_fcg_ref": {"lineage_id": tip["lineage_id"], "bp_id": tip["bp_id"]},
        "objects": objs,
        "verifiers": ["scripts/verify_environment_replay_v1.py", "scripts/verify_final_playthrough_custody_v2.py",
                      "scripts/verify_competition_lineage.py", "tools/verify_mitosis_tenki_claims.py",
                      "scripts/verify_e2e_breakpoints.py"],
        "mitosis_office": OFFICE, "tenki_review_pr": PR3, "created_utc": L.utc()})
    out(E2E_TEST_ID=sid, SEED_FCO_SHA256=h, PARENT_FCG_ROOT=tip["mmr_root"])


def stage_vithia1():
    sid, seed_sha = session_id(), file_sha("evidence/post_submission/e2e/SEED_CHECKPOINT_FCO.json")
    replay = json.loads((E2E / "LOCAL_ENVIRONMENT_REPLAY_RECEIPT.json").read_bytes())
    mem = json.loads((ROOT / "evidence/competition/post_submission/mitosis/MITOSIS_POST_SUBMISSION_VERIFICATION_FCO.json").read_text())
    cand = [  # id, sha, verification_state, why
        ("SeedCheckpointFCO", seed_sha, "PASS", "immutable origin of this session; every referenced object hash-verified at the pinned commit"),
        ("SubmittedSourceRef", SUBMITTED, "PASS", "commit object exists; frozen frame objects byte-identical to HEAD"),
        ("SubmittedPlaythroughCustody", EXPECTED_MMR, "PASS", "scripts/verify_final_playthrough_custody_v2.py: 240 frames, roots equal"),
        ("LocalEnvironmentReplayReceipt", file_sha("evidence/post_submission/e2e/LOCAL_ENVIRONMENT_REPLAY_RECEIPT.json"),
         replay["environment_replay"], "admitted with its true state: pixels/roots/MMR reproduce, PNG-byte step hash does not"),
        ("PNGEncodingMismatchInvestigation", file_sha("evidence/post_submission/e2e/PNG_ENCODING_MISMATCH_INVESTIGATION.json"),
         "PASS", "successor explanation: encoder drift only"),
        ("MitosisHistoricalMemory", HIST_UID, "PASS", "exact-ID get+query verified 2026-09-29 (receipt in repo)"),
        ("MitosisPostSubmissionMemory", PREV_UID, mem["mitosis_persistence_retrieval"], "exact-ID retrieval verified (receipt in repo)"),
        ("TenkiClaimCorrectionFCO", file_sha("evidence/post_submission/e2e/TENKI_CLAIM_CORRECTION_FCO.json"), "PASS", "hash-bound correction of an overstated claim"),
    ]
    rej = [
        {"id": "TenkiSubmittedReplayVerificationFCO(historical)", "reason": "UNSUPPORTED_CLAIM: artifact_reconstruction=PASS without sandbox/source-pin/playthrough execution; superseded by correction FCO"},
        {"id": "SupplementalSeed3Run(score165)", "reason": "NEW_OCCURRENCE: different policy/config than the committed playthrough; not part of submitted evidence"},
        {"id": "TenkiExecutionClaims", "reason": "NOT_EXECUTED: no sandbox has run; nothing to admit"},
    ]
    selected = [{"id": i, "sha256": s, "verification_state": v, "why": w} for i, s, v, w in cand if v in ("PASS", "FAIL")]
    ctx_leaves = [L.hp_ctx(x["id"], x["sha256"], x["verification_state"]) for x in selected]
    ctx_root = L.merkle(ctx_leaves).hex()
    h = L.write_fco(E2E / "VITHIA_PREPROCESSING_FCO.json", {
        "schema": "VithiaPreprocessingFCO_V1", "session_id": sid,
        "input_fco_roots": {"seed_fco_sha256": seed_sha, "local_replay_receipt_sha256": file_sha("evidence/post_submission/e2e/LOCAL_ENVIRONMENT_REPLAY_RECEIPT.json")},
        "selected_context": selected, "rejected_context": rej,
        "anticube_state": "NOT_COMPUTED", "g_star": "NOT_COMPUTED",
        "delta_g_star": {"SeedCheckpointFCO": 0, "note": "origin-relative only (newly frozen origin atom, SELF/SAFE in the origin-relative sense; not a universal safety claim)", "others": "NOT_COMPUTED"},
        "context_root": ctx_root, "predecessor_context_root": "NOT_APPLICABLE_ORIGIN", "created_utc": L.utc()})
    out(VITHIA_PREPROCESSING_FCO_SHA256=h, VITHIA_CONTEXT_ROOT=ctx_root, SELECTED=len(selected), REJECTED=len(rej))


def stage_mitosis_init():
    env = L.load_private_env(ENV_FILE)
    out(MI_API_KEY="SET" if env.get("MI_API_KEY") else "NOT_SET")
    m = L.Mitosis(OFFICE, env)
    a = m.auth()
    out(MITOSIS_AUTH=a["state"], MITOSIS_OFFICE_LIST=a.get("office_list"), MITOSIS_EXPECTED_OFFICE_PRESENT=a.get("expected_office_present"))
    if a["state"] != "PASS":
        return 2
    g = m.get(HIST_UID)
    out(HISTORICAL_GET=g["state"])
    sid = session_id()
    seed_sha = file_sha("evidence/post_submission/e2e/SEED_CHECKPOINT_FCO.json")
    vp = json.loads((E2E / "VITHIA_PREPROCESSING_FCO.json").read_bytes())
    replay = json.loads((E2E / "LOCAL_ENVIRONMENT_REPLAY_RECEIPT.json").read_bytes())
    fact = (f"VITHIA_E2E {sid}: seed_fco_sha256={seed_sha}; submitted_source_commit={SUBMITTED}; "
            f"submitted_playthrough_mmr_root={EXPECTED_MMR}; vithia_context_root={vp['context_root']}; "
            f"local_environment_replay={replay['environment_replay']} (pixels/frame-roots/MMR reproduce; PNG-byte step hash does not); "
            "tenki_execution=NOT_EXECUTED. Immutable E2E test input; universal_id is an address, not a Merkle root.")
    rt = m.roundtrip(fact, f"What are the seed FCO hash, Vithia context root and local replay status for {sid}?")
    out(MITOSIS_INITIAL_WRITE=rt["write"]["state"], MITOSIS_INITIAL_UNIVERSAL_ID=rt["write"].get("universal_id"),
        MITOSIS_INITIAL_QUERY=rt["query"]["state"], MITOSIS_INITIAL_EXACT_ID_MATCH=rt["query"].get("exact_id_match", "NO"),
        MITOSIS_INITIAL_GET=rt["get"]["state"])
    if not (rt["write"]["state"] == rt["query"]["state"] == rt["get"]["state"] == "PASS"):
        return 3
    retrieval = "PASS"
    h = L.write_fco(E2E / "MITOSIS_MEMORY_ANCHOR_FCO.json", {
        "schema": "MitosisMemoryAnchorFCO_V1", "session_id": sid, "universal_id": rt["write"]["universal_id"],
        "seed_fco_sha256": seed_sha, "submitted_source_commit": SUBMITTED, "vithia_context_root": vp["context_root"],
        "retrieval_status": retrieval, "exact_id_match": rt["query"]["exact_id_match"],
        "historical_get_state": g["state"], "office_id": OFFICE, "created_utc": L.utc()})
    out(MITOSIS_MEMORY_ANCHOR_SHA256=h)
    return 0


def stage_pre_tenki():
    e = L.create_breakpoint("PRE_TENKI_BREAKPOINT.json", [
        ("evidence/post_submission/e2e/SEED_CHECKPOINT_FCO.json", "SeedCheckpointFCO", "fco"),
        ("evidence/post_submission/e2e/VITHIA_PREPROCESSING_FCO.json", "VithiaPreprocessingFCO", "fco"),
        ("evidence/post_submission/e2e/MITOSIS_MEMORY_ANCHOR_FCO.json", "MitosisMemoryAnchorFCO", "fco"),
        ("evidence/post_submission/e2e/TENKI_CLAIM_CORRECTION_FCO.json", "TenkiClaimCorrectionFCO", "fco"),
        ("evidence/post_submission/e2e/LOCAL_ENVIRONMENT_REPLAY_RECEIPT.json", "LocalEnvironmentReplayReceipt", "receipt"),
        ("evidence/post_submission/e2e/PNG_ENCODING_MISMATCH_INVESTIGATION.json", "PNGEncodingInvestigation", "receipt"),
        ("evidence/post_submission/e2e/PRE_EXEC_WORKTREE_MANIFEST.json", "PreExecWorktreeManifest", "custody"),
    ])
    rows = L.verify_lineage(e["bp_id"])
    out(PRE_TENKI_BP_ID=e["bp_id"], PRE_TENKI_BP_ROOT=e["bp_root"], PRE_TENKI_MMR_SIZE=e["mmr_size"],
        PRE_TENKI_MMR_ROOT=e["mmr_root_after"], PRE_TENKI_PARENT_ROOT=e["parent_root"],
        PRE_TENKI_BP_VERIFY=rows[-1]["verify_state"])
    return 0 if rows[-1]["verify_state"] == "PASS" else 4


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["correction", "seed", "vithia1", "mitosis-init", "pre-tenki"])
    fn = {"correction": stage_correction, "seed": stage_seed, "vithia1": stage_vithia1,
          "mitosis-init": stage_mitosis_init, "pre-tenki": stage_pre_tenki}[ap.parse_args().stage]
    raise SystemExit(fn() or 0)
