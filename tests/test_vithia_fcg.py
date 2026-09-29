import json, os, stat, subprocess, sys, threading, time
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import vithia_e2e_lib as L
import vithia_fcg as F

GIT = ["git", "-c", "user.email=t@example.com", "-c", "user.name=t"]


def sh(*a, cwd):
    return subprocess.run(list(a), cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def world(tmp_path):
    src = tmp_path / "src"; src.mkdir()
    sh("git", "init", "-q", cwd=src)
    (src / "a.txt").write_text("alpha"); (src / "b.txt").write_text("beta")
    sh(*GIT, "add", ".", cwd=src); sh(*GIT, "commit", "-q", "-m", "seed", cwd=src)
    commit = sh("git", "rev-parse", "HEAD", cwd=src)
    seed = {"schema": "VITHIA_SEED_CHECKPOINT_FCO_V1", "seed_id": "T", "source_commit": commit, "parent_fcg_root": "ab" * 32,
            "expected_mmr_root": "cd" * 32,
            "objects": [{"path": "a.txt", "sha256": L.sha(b"alpha")}, {"path": "b.txt", "sha256": L.sha(b"beta")}],
            "resolvers": {"repository": "https://example.com/r.git", "mitosis_office": "office"},
            "verifiers": [{"name": "custody", "kind": "artifact", "cmd": "x"}, {"name": "env_replay", "kind": "replay", "cmd": "y"}],
            "required_capabilities": [], "optional_deciders": ["scripted"]}
    sf = tmp_path / "seed.json"; sf.write_text(json.dumps(seed, indent=2))
    out = tmp_path / "out"; out.mkdir()
    return dict(src=src, seed=seed, seed_file=sf, out=out, root=L.sha(L.canonical(seed)), tmp=tmp_path)


def session(w, mit=None, ten=None, mode="generate", decider="scripted", sid="S1"):
    seed, root = F.load_seed(w["seed_file"], "sha256:" + w["root"])
    ident = F.make_identity(mode, sid, key_dir=w["tmp"] / "keys")
    return F.Session(w["out"], w["src"], seed, root, sid, mit or F.SimMitosis(), (F.SimTenki() if ten is None else (None if ten is False else ten)), ident, decider, {}, "https://example.com/r.git")


def run_all(s):
    s.phase1(); return s.phase2("SIMULATED_COMMIT")


def test_wrong_seed_hash_stops(world):
    with pytest.raises(F.Stop, match="SEED_FCO_VERIFY=FAIL"):
        F.load_seed(world["seed_file"], "sha256:" + "00" * 32)

def test_root_only_needs_a_resolver(world):
    with pytest.raises(F.Stop, match="SEED_RESOLUTION=BLOCKED"):
        F.load_seed(None, "sha256:" + world["root"], [])
    seed, root = F.load_seed(None, "sha256:" + world["root"], [world["tmp"]])
    assert root == world["root"]

def test_missing_object_stops(world):
    world["seed"]["objects"].append({"path": "nope.txt", "sha256": "00" * 32})
    with pytest.raises(F.Stop, match="OBJECT_RESOLUTION=FAIL: missing"):
        F.verify_source(world["seed"], world["src"])

def test_wrong_object_hash_stops(world):
    world["seed"]["objects"][0]["sha256"] = "11" * 32
    with pytest.raises(F.Stop, match="hash mismatch"):
        F.verify_source(world["seed"], world["src"])

def test_wrong_source_commit_stops(world):
    world["seed"]["source_commit"] = "0" * 40
    with pytest.raises(F.Stop, match="SOURCE_PIN=FAIL"):
        F.verify_source(world["seed"], world["src"])

def test_invalid_mitosis_exact_id_retrieval_fails(world):
    r = run_all(session(world, mit=F.SimMitosis(break_retrieval=True)))
    assert r["mitosis_exact_retrieval"] == "FAIL" and r["mitosis_verification_exact_retrieval"] == "FAIL"
    assert r["portable_agent_memory_load_bearing"] == "NOT_ESTABLISHED"          # nothing retrieved -> nothing consumed

def test_universal_id_as_root_fails():
    with pytest.raises(F.Stop, match="not a root"):
        F.guard_receipt({"final_fcg_mmr_root": "agent:memories:abc"})
    with pytest.raises(ValueError, match="address, not a Merkle"):
        L.validate_fco({**{f: "x" for f in L.SCHEMAS["CheckpointFCO_V1"]}, "schema": "CheckpointFCO_V1", "bp_root": "agent:memories:abc"})

def test_credential_leak_into_fco_fails(tmp_path):
    L.register_secret_values({"s3cr3t-credential-value-9"})
    o = {f: "x" for f in L.SCHEMAS["OutcomeFCO_V1"]}; o.update(schema="OutcomeFCO_V1", outcome="has s3cr3t-credential-value-9")
    with pytest.raises(ValueError, match="KNOWN_SECRET_VALUE"):
        L.write_fco(tmp_path / "o.json", o)
    L._KNOWN_SECRET_VALUES.clear()

def test_private_key_boundary(world, tmp_path):
    s = session(world)
    run_all(s)
    keyfile = world["tmp"] / "keys/S1.ed25519.pem"
    assert keyfile.exists() and stat.S_IMODE(keyfile.stat().st_mode) == 0o600
    assert not str(keyfile).startswith(str(world["out"]))                      # outside the repo/session tree
    marker = "-----BEGIN " + "PRIVATE KEY-----"
    assert marker in keyfile.read_text()
    for f in (world["out"] / "evidence/fcg_sessions/S1").glob("*.json"):
        assert marker not in f.read_text()                                     # never in any artifact
    bad = tmp_path / "leak.txt"; bad.write_text(marker + "\nabc")
    assert L.scan_paths([bad])["state"] == "FAIL"                              # committing it would hard-fail

def test_public_key_only_modes_refuse_private_material():
    with pytest.raises(F.Stop, match="PUBLIC key"):
        F.make_identity("paste", "S", "-----BEGIN " + "PRIVATE KEY-----\nabc")

def test_tenki_local_attribution_confusion_fails():
    base = {"tenki_artifact_verify": "PASS", "tenki_session": "abc", "tenki_provider_mode": "REAL"}
    with pytest.raises(F.Stop, match="non-Tenki execution locus"):
        F.guard_receipt({**base, "tenki_execution_locus": "LOCAL"})
    F.guard_receipt({**base, "tenki_execution_locus": "TENKI_SANDBOX"})

def test_not_executed_cannot_become_pass():
    with pytest.raises(F.Stop, match="without a Tenki session"):
        F.guard_receipt({"tenki_artifact_verify": "PASS", "tenki_session": None, "tenki_provider_mode": "REAL", "tenki_execution_locus": "TENKI_SANDBOX"})
    with pytest.raises(F.Stop, match="not a recognised state"):
        F.guard_receipt({"tenki_source_pin": "OK"})
    with pytest.raises(F.Stop, match="load-bearing claim without"):
        F.guard_receipt({"portable_agent_memory_load_bearing": "PASS"})

def test_no_tenki_adapter_stays_not_executed(world):
    r = run_all(session(world, ten=False))
    assert r["tenki_artifact_verify"] == "NOT_EXECUTED" and r["tenki_environment_replay"] == "NOT_EXECUTED" and r["tenki_session"] is None

def test_checkpoint_parent_mismatch_fails(world):
    s = session(world); s.phase1(); s.phase2("SIMULATED_COMMIT")
    assert all(r["verify_state"] == "PASS" for r in s.lin.verify(s.seed["parent_fcg_root"]))
    bp = s.sdir / "POST_VERIFY_BREAKPOINT.json"; d = json.loads(bp.read_bytes()); d["parent_root"] = "00" * 32; bp.write_bytes(L.canonical(d))
    assert any(r["verify_state"] == "FAIL" for r in s.lin.verify(s.seed["parent_fcg_root"]))

def test_wrong_seed_parent_fails_chain(world):
    s = session(world); s.phase1()
    assert s.lin.verify("ff" * 32)[0]["verify_state"] == "FAIL"

def test_signature_mismatch_fails(world):
    s = session(world); r = run_all(s)
    sig, _ = L.read_fco(s.sdir / "CHECKPOINT_SIGNATURE_FCO.json")
    assert r["checkpoint_signature_state"] == "PASS" and F.verify_signature(sig)
    assert not F.verify_signature({**sig, "root": "00" * 32})
    other = F.make_identity("generate", "S2", key_dir=world["tmp"] / "keys")
    assert not F.verify_signature({**sig, "public_key": other["public_key"], "public_key_fingerprint": other["fingerprint"]})

def test_env_replay_mismatch_is_preserved(world):
    ten = F.SimTenki(replay="FAIL", first_mismatch={"frame": 0, "kind": "PNG_BYTES"})
    s = session(world, ten=ten); r = run_all(s)
    fco, _ = L.read_fco(s.sdir / "TENKI_VERIFICATION_FCO.json")
    assert r["tenki_environment_replay"] == "FAIL" and fco["first_mismatch"] == {"frame": 0, "kind": "PNG_BYTES"}
    assert r["tenki_artifact_verify"] == "PASS"                                # never collapsed into one verdict
    assert r["portable_agent_memory_load_bearing"] == "PASS_BOUNDED"           # artifact tier only

def test_simulated_end_to_end_flow_passes(world):
    s = session(world); r = run_all(s)
    assert r["provider_mode"] == "SIMULATED" and r["secret_scan"] == "PASS" and r["checkpoint_signature_state"] == "PASS"
    assert r["decider"] == "SCRIPTED" and r["mitosis_exact_retrieval"] == "PASS" and r["mitosis_verification_exact_retrieval"] == "PASS"
    assert r["tenki_artifact_verify"] == "PASS" and r["tenki_environment_replay"] == "PASS"
    assert r["portable_agent_memory_load_bearing"] == "PASS_BOUNDED"
    assert len({r["pre_exec_mmr_root"], r["post_verify_mmr_root"], r["final_fcg_mmr_root"]}) == 3
    assert all(x["verify_state"] == "PASS" for x in s.lin.verify(s.seed["parent_fcg_root"]))
    assert r["final_mitosis_universal_id"].startswith("agent:memories:")       # an address, kept out of the root
    assert (s.sdir / "VITHIA_DOCTOR_SESSION_RECEIPT.json").exists()

def test_requested_decider_unavailable_is_blocked_not_substituted(world):
    s = session(world, decider="jev"); r = run_all(s)
    dec, _ = L.read_fco(s.sdir / "DECISION_FCO.json"); out, _ = L.read_fco(s.sdir / "OUTCOME_FCO.json")
    assert dec["status"] == "BLOCKED" and dec["selected_action"] == "NONE" and out["status"] == "NOT_EXECUTED"
    assert r["decider"].startswith("JEV:BLOCKED")

def test_anonymous_identity_has_no_signature(world):
    r = run_all(session(world, mode="anonymous"))
    assert r["operator_identity_mode"] == "ANONYMOUS" and r["checkpoint_signature_state"] == "NOT_USED"

def test_watch_appends_successors_without_mutating(world):
    wd = world["tmp"] / "watched"; wd.mkdir(); (wd / "old.txt").write_text("pre-existing")
    res = []
    t = threading.Thread(target=lambda: res.extend(F.watch(world["out"], "W1", F.SimMitosis(), wd, "ab" * 32, max_events=2, poll=0.05)))
    t.start(); time.sleep(0.3)
    (wd / "n1.txt").write_text("one"); time.sleep(0.3); (wd / "n2.txt").write_text("two"); t.join(10)
    assert len(res) == 2 and res[0]["mmr_root"] != res[1]["mmr_root"]
    lin = F.Lineage(world["out"], world["out"] / "evidence/fcg_sessions/W1/watch", "VITHIA-FCG-WATCH-W1", "ab" * 32)
    assert [r["verify_state"] for r in lin.verify("ab" * 32)] == ["PASS", "PASS"]
