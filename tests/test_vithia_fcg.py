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


def session(w, mit=None, ten=None, mode="generate", decider="scripted", sid="S1", lanes=None, env=None, profile="neutral_v1"):
    seed, root = F.load_seed(w["seed_file"], "sha256:" + w["root"])
    ident = F.make_identity(mode, sid, key_dir=w["tmp"] / "keys")
    return F.Session(w["out"], w["src"], seed, root, sid, mit or F.SimMitosis(), (F.SimTenki() if ten is None else (None if ten is False else ten)), ident, decider, env or {}, "https://example.com/r.git", lanes=lanes, profile=profile)


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


# ---------------------------------------------------------------- lanes / prompt profiles / OpenJEV contract
import http.server, socketserver


def serve(handler):
    """Tiny local HTTP stub; handler(path, headers, body_dict) -> (status, json_obj)."""
    seen = []
    class H(http.server.BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen.append({"path": self.path, "auth": self.headers.get("Authorization"), "body": body})
            code, obj = handler(self.path, self.headers, body)
            raw = json.dumps(obj).encode(); self.send_response(code); self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)
        def log_message(self, *a): pass
    srv = socketserver.TCPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f"http://127.0.0.1:{srv.server_address[1]}", srv, seen


def ollama_stub(by_model):
    return serve(lambda p, h, b: (200, {"model": b["model"], "message": {"content": json.dumps({"action": by_model[b["model"]]})}}))


def test_parse_lanes_handles_colons_and_rejects_bad_specs():
    ls = F.parse_lanes("scripted,ollama:hf.co/Liquid/LFM:Q4_K_M,ollama:qwen3:1.7b,openjev")
    assert [x["kind"] for x in ls] == ["scripted", "ollama", "ollama", "openjev"] and ls[1]["model"] == "hf.co/Liquid/LFM:Q4_K_M" and ls[2]["model"] == "qwen3:1.7b"
    assert all("/" not in x["name"] and ":" not in x["name"] for x in ls)
    with pytest.raises(F.Stop, match="duplicate"): F.parse_lanes("scripted,scripted")
    with pytest.raises(F.Stop, match="unknown decider"): F.parse_lanes("gpt")

def test_lanes_share_one_context_root_and_overreach_is_blocked_per_lane(world):
    base, srv, seen = ollama_stub({"overclaimer": F.ONTOLOGY[0], "careful": F.ONTOLOGY[2]})
    lanes = F.parse_lanes("scripted,ollama:overclaimer,ollama:careful,skip")
    s = session(world, ten=F.SimTenki(replay="FAIL", first_mismatch={"frame": 0, "kind": "PNG_BYTES"}), lanes=lanes, env={"OLLAMA_BASE_URL": base}); r = run_all(s); srv.shutdown()
    L_ = {x["lane"]: x for x in r["lanes"]}
    assert r["input_context_root_shared"] == "YES" and len({x["input_context_root"] for x in r["lanes"]}) == 1
    assert r["context_ceiling"] == F.ONTOLOGY[1]                                       # artifact PASS, replay FAIL
    assert L_["scripted"]["action"] == F.ONTOLOGY[1] and L_["scripted"]["supported_by_context"] == "YES" and L_["scripted"]["executed"]
    assert L_["ollama_overclaimer"]["supported_by_context"] == "NO" and not L_["ollama_overclaimer"]["executed"]
    assert L_["ollama_careful"]["supported_by_context"] == "YES" and L_["skip"]["supported_by_context"] == "NOT_APPLICABLE"
    oc, _ = L.read_fco(s.sdir / "OUTCOME_FCO__ollama_overclaimer.json"); assert oc["status"] == "BLOCKED" and oc["outcome"] == "CLAIM_OVERREACH_REFUSED"
    ledger = json.loads((s.sdir / "FCG_MMR_LEDGER.json").read_bytes()); fin = json.loads((ROOT_ := world["out"] / ledger["entries"][-1]["bp_file"]).read_bytes())
    paths = {a["path"].rsplit("/", 1)[1] for a in fin["atoms"]}
    assert {"DECISION_FCO.json", "DECISION_FCO__ollama_overclaimer.json", "OUTCOME_FCO__ollama_careful.json", "ACTION_EXECUTION_FCO__skip.json"} <= paths
    assert all(x["verify_state"] == "PASS" for x in s.lin.verify(s.seed["parent_fcg_root"]))
    assert {q["body"]["model"] for q in seen} == {"overclaimer", "careful"}

def test_unavailable_lane_is_blocked_and_never_replaced_by_another(world):
    lanes = F.parse_lanes("ollama:whatever,scripted")
    r = run_all(session(world, lanes=lanes, env={"OLLAMA_BASE_URL": "http://127.0.0.1:9"}))
    L_ = {x["lane"]: x for x in r["lanes"]}
    assert L_["ollama_whatever"]["status"] == "BLOCKED" and L_["ollama_whatever"]["action"] is None and L_["ollama_whatever"]["provider"] == "ollama"
    assert L_["scripted"]["status"] == "PASS"                                          # other lanes unaffected

def test_openjev_adapter_uses_bearer_token_and_choice_question_shape():
    tok = "local-shim-" + "t0k3n"
    base, srv, seen = serve(lambda p, h, b: (200, {"model": "openjev-MLX-4bit", "answers": {"action": {"choice": F.ONTOLOGY[2], "confidence": 0.7}}}))
    d = F.run_decider("openjev", {"artifact_reconstruction": "NOT_ESTABLISHED", "environment_replay": "NOT_ESTABLISHED"}, {"OPENJEV_BASE_URL": base, "OPENJEV_TOKEN": tok}); srv.shutdown()
    q = seen[0]
    assert d["status"] == "PASS" and d["action"] == F.ONTOLOGY[2] and d["provider"] == "openjev-local:openjev-MLX-4bit"
    assert q["path"] == "/v1/systemone" and q["auth"] == "Bearer " + tok
    qq = q["body"]["questions"]["action"]
    assert qq["type"] == "choice" and set(qq["criteria"]) == set(F.ONTOLOGY) and q["body"]["state"]["verification_status"]
    assert tok not in json.dumps(d)                                                   # token never appears in the result

def test_openjev_401_is_blocked_with_the_http_code_not_a_fallback():
    base, srv, _ = serve(lambda p, h, b: (401, {"error": "unauthorized"}))
    d = F.run_decider("openjev", {"artifact_reconstruction": "NOT_ESTABLISHED", "environment_replay": "NOT_ESTABLISHED"}, {"OPENJEV_BASE_URL": base, "OPENJEV_TOKEN": "x"}); srv.shutdown()
    assert d["status"] == "BLOCKED" and d["action"] is None and "HTTPError:401" in d["note"]

def test_prompt_profiles_are_frozen_hashed_and_recorded(world):
    assert F.prompt_sha("neutral_v1") != F.prompt_sha("explicit_v1")
    base, srv, seen = ollama_stub({"m": F.ONTOLOGY[2]})
    lanes = F.parse_lanes("ollama:m")
    s1 = session(world, lanes=lanes, env={"OLLAMA_BASE_URL": base}, profile="neutral_v1", sid="P1"); run_all(s1)
    s2 = session(world, lanes=lanes, env={"OLLAMA_BASE_URL": base}, profile="explicit_v1", sid="P2"); run_all(s2); srv.shutdown()
    d1, _ = L.read_fco(s1.sdir / "DECISION_FCO.json"); d2, _ = L.read_fco(s2.sdir / "DECISION_FCO.json")
    assert d1["prompt_profile"] == "neutral_v1" and d1["prompt_sha256"] == F.prompt_sha("neutral_v1") and d2["prompt_sha256"] == F.prompt_sha("explicit_v1")
    c1 = seen[0]["body"]["messages"][0]["content"]; c2 = seen[2]["body"]["messages"][0]["content"]   # each session: lane-0 request + its counterfactual
    assert c1.startswith("Choose exactly one action. Reply JSON") and '"actions": ["PUBLISH' in c1          # identical to the first rehearsal's wording
    assert "Rule:" in c2 and "requires" in c2 and "Rule:" not in c1


def test_openjev_refuses_non_loopback_endpoint_and_never_sends_the_token():
    base, srv, seen = serve(lambda p, h, b: (200, {"answers": {"action": {"choice": F.ONTOLOGY[2]}}}))
    for bad in ("http://example.com:8765", "https://10.0.0.5:8771", "http://127.0.0.1.evil.example:8765"):
        d = F.run_decider("openjev", {"artifact_reconstruction": "NOT_ESTABLISHED", "environment_replay": "NOT_ESTABLISHED"}, {"OPENJEV_BASE_URL": bad, "OPENJEV_TOKEN": "secret-shim-token"})
        assert d["status"] == "BLOCKED" and "non-loopback" in d["note"]
    srv.shutdown(); assert seen == []


# ---------------------------------------------------------------- PR #7 review fixes
def test_existing_session_directory_is_never_reused(world):
    s = session(world, sid="DUP"); run_all(s)
    before = {p.name: p.read_bytes() for p in s.sdir.iterdir()}
    with pytest.raises(F.Stop, match="SESSION_DIR_EXISTS"):
        session(world, sid="DUP")
    assert {p.name: p.read_bytes() for p in s.sdir.iterdir()} == before                     # prior evidence untouched

class _Tenki(F.SimTenki):
    """SimTenki whose per-command stdout / exit codes / receipt can be overridden."""
    def __init__(self, edit, **kw):
        super().__init__(**kw); self.edit = edit
    def execute(self, *a):
        r = super().execute(*a); self.edit(r); return r

def test_recomputed_root_comes_only_from_artifact_verifiers(world):
    wrong = json.dumps({"recomputed_mmr_root": "ee" * 32})
    def replay_prints_other_root(r):                       # replay verifier prints a different root: must not affect artifact reconstruction
        next(c for c in r["commands"] if c["name"] == "env_replay")["stdout_tail"] = wrong
    assert run_all(session(world, ten=_Tenki(replay_prints_other_root)))["tenki_artifact_verify"] == "PASS"
    def artifact_prints_wrong_root(r):                     # artifact verifier exits 0 but its root is wrong: cannot be rescued by the replay verifier
        next(c for c in r["commands"] if c["name"] == "custody")["stdout_tail"] = wrong
    assert run_all(session(world, ten=_Tenki(artifact_prints_wrong_root), sid="S2"))["tenki_artifact_verify"] == "FAIL"

def test_disagreeing_artifact_roots_do_not_pass(world):
    seed = world["seed"]; seed["verifiers"].append({"name": "second", "kind": "artifact", "cmd": "z"})
    world["seed_file"].write_text(json.dumps(seed)); world["root"] = L.sha(L.canonical(seed))
    def second_disagrees(r):
        r["commands"].append({"name": "second", "exit_code": 0, "stdout_tail": json.dumps({"recomputed_mmr_root": "ee" * 32})})
    assert run_all(session(world, ten=_Tenki(second_disagrees)))["tenki_artifact_verify"] == "FAIL"

def test_replay_pass_requires_successful_command_and_expected_root(world):
    def receipt_pass_but_command_failed(r):
        next(c for c in r["commands"] if c["name"] == "env_replay")["exit_code"] = 1
    assert run_all(session(world, ten=_Tenki(receipt_pass_but_command_failed)))["tenki_environment_replay"] == "FAIL"
    def receipt_pass_wrong_root(r):
        r["receipts"]["env_replay"]["recomputed_mmr_root"] = "ee" * 32
    assert run_all(session(world, ten=_Tenki(receipt_pass_wrong_root), sid="S2"))["tenki_environment_replay"] == "FAIL"
    def receipt_pass_unpinned(r):
        r["source_pin"] = "FAIL"
    assert run_all(session(world, ten=_Tenki(receipt_pass_unpinned), sid="S3"))["tenki_environment_replay"] == "FAIL"
    assert run_all(session(world, sid="S4"))["tenki_environment_replay"] == "PASS"          # the honest case still passes

def _ctx_stub(sensitive):
    """Ollama stub: a context-insensitive model always answers ARTIFACT_ONLY; a sensitive one withholds unless the context shows artifact PASS."""
    def h(path, headers, body):
        content = body["messages"][0]["content"]
        act = F.ONTOLOGY[1] if (not sensitive or '"artifact_reconstruction": "PASS"' in content) else F.ONTOLOGY[2]
        return 200, {"model": body["model"], "message": {"content": json.dumps({"action": act})}}
    return serve(h)

def test_load_bearing_needs_the_same_decider_to_change_its_own_answer(world):
    base, srv, _ = _ctx_stub(sensitive=False)
    r = run_all(session(world, lanes=F.parse_lanes("ollama:m"), env={"OLLAMA_BASE_URL": base}, sid="LB1")); srv.shutdown()
    assert r["lanes"][0]["action"] == F.ONTOLOGY[1] and r["portable_agent_memory_load_bearing"] == "NOT_ESTABLISHED"   # differs from scripted WITHHOLD, but memory had no effect on THIS model
    base, srv, _ = _ctx_stub(sensitive=True)
    r = run_all(session(world, lanes=F.parse_lanes("ollama:m"), env={"OLLAMA_BASE_URL": base}, sid="LB2")); srv.shutdown()
    assert r["portable_agent_memory_load_bearing"] == "PASS_BOUNDED"
    lb = json.loads((world["out"] / "evidence/fcg_sessions/LB2/LOAD_BEARING_RECEIPT.json").read_bytes())
    assert lb["counterfactual_decider"] == "ollama" and lb["decision_without_memory"] == F.ONTOLOGY[2] and lb["decision_with_memory"] == F.ONTOLOGY[1]

def test_load_bearing_not_established_when_counterfactual_lane_is_blocked(world):
    r = run_all(session(world, lanes=F.parse_lanes("ollama:m"), env={"OLLAMA_BASE_URL": "http://127.0.0.1:9"}, sid="LB3"))
    assert r["portable_agent_memory_load_bearing"] == "NOT_ESTABLISHED"

def test_remote_mode_forwards_every_parsed_option_shell_quoted():
    out = subprocess.run(["bash", "tools/vithia_doctor3.sh", "--remote", "studio.local", "--simulate", "--non-interactive", "--seed-fco", "a b.json",
                          "--resolver-dir", "d", "--identity-mode", "generate", "--session-id", "S9", "--decider", "ollama", "--deciders", "scripted,ollama:m",
                          "--prompt-profile", "explicit_v1", "--env-file", "/x y/.env", "--_print-forward-args"],
                         cwd=Path(__file__).resolve().parents[1], capture_output=True, text=True).stdout.strip()
    for want in ("--simulate", "--non-interactive", "--seed-fco a\\ b.json", "--resolver-dir d", "--identity-mode generate", "--session-id S9", "--deciders scripted\\,ollama:m",
                 "--prompt-profile explicit_v1", "--env-file /x\\ y/.env"):
        assert want in out, (want, out)
    assert "--remote" not in out and "studio.local" not in out
