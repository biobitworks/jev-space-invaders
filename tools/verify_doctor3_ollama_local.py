#!/usr/bin/env python3
"""Doctor3 local-Ollama end-to-end portability verification (machine-run, no sponsor credentials).

Run from inside a fresh clone on the target host:
    python3 tools/verify_doctor3_ollama_local.py [--model NAME] [--previous-host magicPRObox] [--setup-venv] [--no-second-model]

It never installs or downloads a model, never signs into Ollama cloud, never calls a sponsor API, and removes every
provider credential from the Doctor3 child environment. Every state is reported as found; nothing is normalised to PASS.
Doctor3 itself commits and pushes the session evidence; this script then commits only its own report file.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import stat
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip())
sys.path.insert(0, str(ROOT / "tools"))

SEED_REL = "evidence/fcg_seeds/UFA_JEV_SUBMITTED_PLAYTHROUGH_240_V1.seed.json"
EXPECTED_SEED_ROOT = "sha256:45d04e0d2da5f0c1255844b011bb2576320e1ff5517f0e38d8e79b8899a88bc8"
EXPECTED_SOURCE = "4c943a92e84d0fb2cd3d01e4fdf15a10991eda71"
EXPECTED_BRANCH = "postsubmission/vithia-doctor3-v01"
CRED_VARS = ["MI_API_KEY", "MITOSIS_API_KEY", "TENKI_API_KEY", "TENKI_AUTH_TOKEN", "TYPESAFE_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"]
BASE = "http://127.0.0.1:11434"
TIER = {"WITHHOLD_ALL_TENKI_CLAIMS": 0, "PUBLISH_CLAIM_ARTIFACT_VERIFIED_ONLY": 1, "PUBLISH_CLAIM_REPLAY_COMPLETE": 2}


def sh(*a, env=None, check=False):
    p = subprocess.run(list(a), cwd=ROOT, capture_output=True, text=True, env=env)
    if check and p.returncode:
        raise RuntimeError(f"{a[0]} failed: {p.stderr.strip()[:300]}")
    return p


def http_json(url, body=None, timeout=180):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body else None, headers={"Content-Type": "application/json"})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read())


def is_cloud(m: dict) -> bool:
    n = m.get("name", "")
    return bool(m.get("remote_host") or m.get("remote_model")) or ":cloud" in n or n.endswith("-cloud")


def choose_models(tags: list[dict], forced: str | None) -> list[str]:
    local = [m for m in tags if not is_cloud(m) and "embed" not in m["name"]]
    names = [m["name"] for m in sorted(local, key=lambda m: m.get("size", 0))]
    if forced:
        return [forced] if forced in names else []
    first = "llama3.2:3b" if "llama3.2:3b" in names else (names[0] if names else None)
    rest = [n for n in names if n != first and not re.search(r"deepseek-r1|phi4-reasoning|qwen3", n)]
    return ([first] if first else []) + rest[:1]


def direct_smoke(model: str) -> dict:
    prompt = ('Choose exactly one action from ["PUBLISH_CLAIM_REPLAY_COMPLETE","PUBLISH_CLAIM_ARTIFACT_VERIFIED_ONLY","WITHHOLD_ALL_TENKI_CLAIMS"]. '
              'No sponsor verification has been established. Reply with strict JSON only: {"action": "<one of the list>"}')
    try:
        r = http_json(BASE + "/api/chat", {"model": model, "stream": False, "format": "json", "options": {"temperature": 0},
                                           "messages": [{"role": "user", "content": prompt}]})
        parsed = json.loads(r["message"]["content"])
        ok = isinstance(parsed, dict) and parsed.get("action") in TIER
        return {"state": "PASS" if ok else "FAIL", "actual_model": r.get("model"), "action": parsed.get("action") if isinstance(parsed, dict) else None}
    except Exception as e:  # noqa: BLE001
        return {"state": "BLOCKED", "actual_model": None, "error": type(e).__name__}


def wiring_check(F) -> dict:
    src = (ROOT / "tools/vithia_fcg.py").read_text()
    body = src[src.index("def run_decider"):src.index("# ---------------------------------------------------------------- claim guard")]
    static = {"ollama_supported": 'kind == "ollama"' in body, "default_endpoint_loopback": "http://127.0.0.1:11434" in body,
              "model_from_OLLAMA_MODEL": 'env.get("OLLAMA_MODEL"' in body, "temperature_0": '"temperature": 0' in body,
              "ontology_enforced": "cand in ONTOLOGY" in body, "exceptions_blocked": '"status": "BLOCKED"' in body and "except Exception" in body}
    dead = F.run_decider("ollama", {"artifact_reconstruction": "NOT_ESTABLISHED", "environment_replay": "NOT_ESTABLISHED"},
                         {"OLLAMA_BASE_URL": "http://127.0.0.1:9", "OLLAMA_MODEL": "x"})
    behaviour = {"unreachable_server_is_BLOCKED": dead["status"] == "BLOCKED", "no_action_on_failure": dead["action"] is None,
                 "no_fallback_provider": dead["provider"] == "ollama"}
    ok = all(static.values()) and all(behaviour.values())
    return {"state": "PASS" if ok else "FAIL", "static": static, "behaviour": behaviour}


def run_session(model: str | None, sid: str, env_base: dict, lanes: str | None = None, profile: str | None = None) -> dict:
    env = {k: v for k, v in env_base.items() if k not in CRED_VARS}          # deliberately no credentials
    env.update(OLLAMA_BASE_URL=BASE)
    if model:
        env["OLLAMA_MODEL"] = model
    cmd = ["bash", "tools/vithia_doctor3.sh", "--seed-fco", SEED_REL, "--non-interactive", "--identity-mode", "generate", "--session-id", sid]
    cmd += ["--deciders", lanes] if lanes else ["--decider", "ollama"]
    if profile:
        cmd += ["--prompt-profile", profile]
    p = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
    return {"rc": p.returncode, "out": p.stdout, "err": p.stderr[-600:]}


def kv(out: str, key: str):
    m = re.findall(rf"^{key}=(.*)$", out, re.M)
    return m[-1].strip() if m else None


def verify_session(F, L, sid: str) -> dict:
    sd = ROOT / "evidence/fcg_sessions" / sid
    r = json.loads((sd / "VITHIA_DOCTOR_SESSION_RECEIPT.json").read_bytes())
    seed, _ = F.load_seed(sd / "SEED_CHECKPOINT_FCO.json", None)
    rows = F.Lineage(ROOT, sd, f"VITHIA-FCG-{sid}", seed["parent_fcg_root"]).verify(seed["parent_fcg_root"])
    chain = all(x["verify_state"] == "PASS" for x in rows) and rows[-1]["recomputed_root"] == r["final_fcg_mmr_root"]
    sig_ok, sig = "NOT_USED", None
    if (sd / "CHECKPOINT_SIGNATURE_FCO.json").exists():
        sig, _ = L.read_fco(sd / "CHECKPOINT_SIGNATURE_FCO.json")
        sig_ok = "PASS" if (F.verify_signature(sig) and sig["root"] == r["final_fcg_mmr_root"] and sig["public_key_fingerprint"] == r["operator_public_key_fingerprint"]) else "FAIL"
    dec, dh = L.read_fco(sd / "DECISION_FCO.json"); act, ah = L.read_fco(sd / "ACTION_EXECUTION_FCO.json"); out, oh = L.read_fco(sd / "OUTCOME_FCO.json")
    vctx, _ = L.read_fco(sd / "VITHIA_VERIFIED_CONTEXT_FCO.json")
    ceiling = F.policy_scripted(vctx["verification_status"])
    supported = "YES" if dec["selected_action"] in TIER and TIER[dec["selected_action"]] <= TIER[ceiling] else "NO"
    key = Path.home() / ".vithia/identities" / f"{sid}.ed25519.pem"
    mode = oct(stat.S_IMODE(key.stat().st_mode))[2:] if key.exists() else None
    marker = "-----BEGIN " + "PRIVATE KEY-----"
    in_fco = any(marker in f.read_text() for f in sd.glob("*.json"))
    tracked = sh("git", "ls-files").stdout.splitlines()
    committed = any(t.endswith(".ed25519.pem") for t in tracked) or bool(sh("git", "grep", "-l", marker, "--", "evidence").stdout.strip())
    return {"receipt": r, "chain": "PASS" if chain else "FAIL", "final_bp_verify": rows[-1]["verify_state"], "sig_verify": sig_ok, "decision": dec, "decision_sha": dh,
            "action_sha": ah, "outcome_sha": oh, "action_status": act["status"], "outcome_status": out["status"], "ceiling": ceiling, "supported": supported,
            "key_mode": mode, "key_in_fco": "YES" if in_fco else "NO", "key_committed": "YES" if committed else "NO",
            "scan": L.scan_paths(list(sd.glob("*.json")))["state"], "mmr_size": r["final_fcg_mmr_size"]}


def openjev_precheck() -> dict:
    import vithia_fcg as F
    base = os.environ.get("OPENJEV_BASE_URL")
    open_ports = []
    if not base:
        for port in range(8765, 8776):
            with socket.socket() as sk:
                sk.settimeout(0.3)
                if sk.connect_ex(("127.0.0.1", port)) == 0:
                    open_ports.append(port)
    return {"OPENJEV_BASE_URL_env": base or "UNSET(default http://127.0.0.1:8765)", "loopback_ports_listening_8765_8775_UNVERIFIED_IDENTITY": open_ports,
            "bearer_token_present": bool(F.openjev_token(dict(os.environ))),
            "hint": ("a listening port does NOT prove it is OpenJEV (another local service can hold it). The authoritative endpoint is the one recorded by "
                     "`python scripts/openjev_runtime.py status` (needs the OpenJEV runtime started with `serve`); export OPENJEV_BASE_URL to it explicitly")}


def lanes_mode(a, R, F, L, host, tags) -> int:
    lanes = F.parse_lanes(a.lanes)
    R["LANES_REQUESTED"] = [x["name"] for x in lanes]; R["PROMPT_PROFILE"] = a.prompt_profile
    by = {m["name"]: m for m in tags}
    pre = {}
    for ln in lanes:
        if ln["kind"] == "ollama":
            m = ln["model"]
            if not m:
                R["BLOCKED"] = "ollama lane without an explicit model (use ollama:<model>)"; print_report(R); return 2
            if m in by and is_cloud(by[m]):
                R["BLOCKED"] = f"lane model {m} is cloud-tagged; refusing"; print_report(R); return 2
            pre[ln["name"]] = {"installed": m in by, "smoke": direct_smoke(m)["state"] if m in by else "NOT_INSTALLED"}
        elif ln["kind"] == "openjev":
            pre[ln["name"]] = openjev_precheck()
    R["LANE_PRECHECKS"] = pre
    if any(x["kind"] == "ollama" for x in lanes):
        w = wiring_check(F); R["OLLAMA_ADAPTER_WIRING"] = w["state"]
        if w["state"] != "PASS":
            R["BLOCKED"] = "adapter wiring check failed; Doctor3 not run"; print_report(R); return 2
    sid = f"FCG-LANES-{re.sub(r'[^A-Za-z0-9]', '', host)[:14]}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
    run = run_session(None, sid, dict(os.environ), lanes=a.lanes, profile=a.prompt_profile)
    if run["rc"] != 0:
        R["BLOCKED"] = f"Doctor3 exited {run['rc']}: {run['err'][:200]}"; print_report(R); return 2
    v = verify_session(F, L, sid); r = v["receipt"]
    R.update(SEED_RESOLUTION=kv(run["out"], "SEED_RESOLUTION"), SOURCE_PIN=r["source_pin"], VITHIA_PREPROCESSING=r["vithia_preprocessing"], PRE_EXEC_BP=r["pre_exec_breakpoint"],
             PRE_EXEC_MMR_ROOT=r["pre_exec_mmr_root"], PRE_EXEC_VERIFY=r["pre_exec_verify"], OPERATOR_IDENTITY_MODE=r["operator_identity_mode"],
             PUBLIC_KEY_FINGERPRINT=r["operator_public_key_fingerprint"], PRIVATE_KEY_MODE=v["key_mode"], PRIVATE_KEY_COMMITTED=v["key_committed"], PRIVATE_KEY_IN_FCO=v["key_in_fco"],
             MITOSIS_AUTH=r["mitosis_auth"], TENKI_AUTH=r["tenki_auth"], HOSTED_JEV="NOT_EXECUTED", VERIFIED_CONTEXT_ROOT=r["verified_context_root"],
             CONTEXT_CEILING=r["context_ceiling"], SAME_INPUT_CONTEXT_ROOT_ACROSS_LANES=r["input_context_root_shared"], FINAL_FCG_BP=r["final_fcg_breakpoint"],
             FINAL_FCG_ROOT=r["final_fcg_mmr_root"], FINAL_MMR_SIZE=v["mmr_size"], PARENT_CHAIN_VERIFY=v["chain"], FINAL_FCG_BP_VERIFY=v["final_bp_verify"],
             CHECKPOINT_SIGNATURE_STATE=r["checkpoint_signature_state"], CHECKPOINT_SIGNATURE_VERIFY=v["sig_verify"],
             SECRET_SCAN=("PASS" if (v["scan"] == "PASS" and sh(sys.executable, "scripts/secret_scan.py").returncode == 0) else "FAIL"))
    R["LANES"] = [{"lane": x["lane"], "provider": x["provider"], "status": x["status"], "action": x["action"], "supported_by_context": x["supported_by_context"],
                   "latency_ms": x["latency_ms"], "executed": x["executed"], "note": x["note"], "input_context_root": x["input_context_root"][:16] + "…",
                   "decision_fco_sha256": x["decision_fco_sha256"], "outcome_fco_sha256": x["outcome_fco_sha256"]} for x in r["lanes"]]
    R["LANES_CLAIM_GATE_INTEGRITY"] = "PASS" if not any(x["supported_by_context"] == "NO" and x["executed"] for x in r["lanes"]) else "FAIL"
    infra = [R["PARENT_CHAIN_VERIFY"] == "PASS", R["FINAL_FCG_BP_VERIFY"] == "PASS", R["CHECKPOINT_SIGNATURE_VERIFY"] == "PASS", R["SECRET_SCAN"] == "PASS",
             R["PRE_EXEC_VERIFY"] == "PASS", R["PRIVATE_KEY_MODE"] == "600", R["PRIVATE_KEY_COMMITTED"] == "NO", R["PRIVATE_KEY_IN_FCO"] == "NO", R["SOURCE_PIN"] == "PASS",
             R["SEED_ROOT_MATCH"] == "PASS", R["SAME_INPUT_CONTEXT_ROOT_ACROSS_LANES"] == "YES", R["LANES_CLAIM_GATE_INTEGRITY"] == "PASS"]
    same_host = a.previous_host.lower() in host.lower() or a.previous_host.lower() in socket.gethostname().lower()
    R["INVARIANTS_MATCH_PREVIOUS_RUN"] = {"seed_root": R["SEED_ROOT"] == EXPECTED_SEED_ROOT, "source_commit": R["SOURCE_COMMIT"] == EXPECTED_SOURCE, "final_root_may_differ": True}
    R["DOCTOR3_CROSS_MACHINE_PORTABILITY"] = ("PASS_BOUNDED" if (all(infra) and not same_host) else
                                             (f"NOT_ESTABLISHED_SAME_HOST_AS_PREVIOUS_RUN (infrastructure checks: {'PASS' if all(infra) else 'FAIL'})" if same_host else "FAIL"))
    R["NOTE"] = "Lane decisions are recorded, not ranked; an unsupported lane decision is a model finding, and the claim gate refusing it is the intended behaviour."
    rep = ROOT / "evidence/fcg_sessions" / sid / "PORTABILITY_VERIFICATION_REPORT.json"
    L.scan_text(json.dumps(R), "portability report"); rep.write_text(json.dumps(R, indent=2, sort_keys=True) + "\n")
    R["COMMIT"] = R["PUSH"] = "NOT_ATTEMPTED"
    if not a.no_push:
        sh("git", "add", "--", str(rep.relative_to(ROOT)))
        c = sh("git", "commit", "-q", "-m", f"evidence: doctor3 lane comparison report ({sid})")
        R["COMMIT"] = sh("git", "rev-parse", "HEAD").stdout.strip() if c.returncode == 0 else f"FAILED:{c.stderr.strip()[:100]}"
        pu = sh("git", "push", "-q", "origin", a.expected_branch); sh("git", "fetch", "origin")
        R["PUSH"] = "PASS" if pu.returncode == 0 else f"FAILED:{pu.stderr.strip()[:100]}"
        R["FINAL_ORIGIN_PARITY"] = "PASS" if sh("git", "rev-parse", "HEAD").stdout == sh("git", "rev-parse", f"origin/{a.expected_branch}").stdout else "FAIL"
    print_report(R)
    return 0 if all(infra) else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model"); ap.add_argument("--previous-host", default="magicPRObox"); ap.add_argument("--expected-branch", default=EXPECTED_BRANCH)
    ap.add_argument("--lanes", help="one session, many deciders on one shared verified context, e.g. scripted,ollama:llama3.2:3b,openjev")
    ap.add_argument("--prompt-profile", default="neutral_v1")
    ap.add_argument("--setup-venv", action="store_true"); ap.add_argument("--no-second-model", action="store_true"); ap.add_argument("--no-push", action="store_true")
    a = ap.parse_args()
    R: dict = {}
    host = sh("scutil", "--get", "ComputerName").stdout.strip() or socket.gethostname()
    R["HOST"] = host
    # --- repo
    sh("git", "fetch", "origin")
    R["BRANCH"] = sh("git", "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if R["BRANCH"] != a.expected_branch:
        R["BLOCKED"] = f"on branch {R['BRANCH']}, expected {a.expected_branch}"; print_report(R); return 2
    dirty = sh("git", "status", "--porcelain", "--untracked-files=no").stdout.strip()
    R["WORKTREE"] = "CLEAN" if not dirty else "TRACKED_DIRTY"
    if dirty:
        R["BLOCKED"] = "tracked files are dirty; refusing to proceed"; print_report(R); return 2
    sh("git", "pull", "--ff-only")
    R["HEAD"] = sh("git", "rev-parse", "HEAD").stdout.strip(); R["ORIGIN_HEAD"] = sh("git", "rev-parse", f"origin/{a.expected_branch}").stdout.strip()
    R["ORIGIN_PARITY"] = "PASS" if R["HEAD"] == R["ORIGIN_HEAD"] else "FAIL"
    if R["ORIGIN_PARITY"] != "PASS":
        R["BLOCKED"] = "origin parity failed"; print_report(R); return 2
    # --- python deps (fresh clone): never silent
    py = ROOT / ".venv/bin/python"
    try:
        import cryptography  # noqa: F401
    except ImportError:
        if not py.exists() and a.setup_venv:
            sh("python3", "-m", "venv", ".venv", check=True); sh(str(py), "-m", "pip", "install", "-q", "cryptography", check=True)
        if py.exists():
            os.execv(str(py), [str(py)] + sys.argv)
        R["BLOCKED"] = "python 'cryptography' missing; re-run with --setup-venv (creates .venv and installs only 'cryptography')"; print_report(R); return 2
    import vithia_fcg as F, vithia_e2e_lib as L
    # --- seed / source
    try:
        seed, root = F.load_seed(ROOT / SEED_REL, EXPECTED_SEED_ROOT)
        R["SEED_FCO_VERIFY"] = "PASS"; R["SEED_ROOT"] = "sha256:" + root; R["SEED_ROOT_MATCH"] = "PASS" if "sha256:" + root == EXPECTED_SEED_ROOT else "FAIL"
        R["SOURCE_COMMIT"] = seed["source_commit"]
        if seed["source_commit"] != EXPECTED_SOURCE:
            R["BLOCKED"] = "seed source commit differs from the frozen commit"; print_report(R); return 2
    except F.Stop as e:
        R["SEED_FCO_VERIFY"] = "FAIL"; R["BLOCKED"] = str(e); print_report(R); return 2
    # --- ollama
    R["OLLAMA_BINARY"] = sh("bash", "-c", "command -v ollama").stdout.strip() or "NOT_FOUND"
    R["OLLAMA_VERSION"] = (sh("ollama", "--version").stdout or sh("ollama", "--version").stderr).strip().splitlines()[0] if R["OLLAMA_BINARY"] != "NOT_FOUND" else "NOT_FOUND"
    try:
        tags = http_json(BASE + "/api/tags", timeout=10)["models"]; R["OLLAMA_SERVER"] = "UP_LOOPBACK_11434"
    except Exception as e:  # noqa: BLE001
        R["OLLAMA_SERVER"] = f"DOWN:{type(e).__name__}"; R["BLOCKED"] = "local Ollama server not reachable"; print_report(R); return 2
    R["OLLAMA_MODELS_AVAILABLE"] = [m["name"] for m in tags]
    if a.lanes:
        return lanes_mode(a, R, F, L, host, tags)
    models = choose_models(tags, a.model)
    if not models:
        R["BLOCKED"] = "no suitable already-installed non-cloud model"; print_report(R); return 2
    R["OLLAMA_MODEL"] = models[0]
    sm = direct_smoke(models[0])
    R["OLLAMA_DIRECT_SMOKE"] = sm["state"]; R["OLLAMA_MODEL_ACTUAL"] = sm["actual_model"]
    R["OLLAMA_LOCAL_ONLY"] = "YES" if (BASE.startswith("http://127.0.0.1") and not next((is_cloud(m) for m in tags if m["name"] == models[0]), True)) else "NO"
    w = wiring_check(F); R["OLLAMA_ADAPTER_WIRING"] = w["state"]; R["OLLAMA_ADAPTER_WIRING_DETAIL"] = {**w["static"], **w["behaviour"]}
    if sm["state"] != "PASS" or R["OLLAMA_LOCAL_ONLY"] != "YES" or w["state"] != "PASS":
        R["BLOCKED"] = "precondition failed (direct smoke / local-only / adapter wiring); Doctor3 not run"; print_report(R); return 2
    # --- sessions
    sessions = []
    for i, model in enumerate(models if not a.no_second_model else models[:1]):
        sid = f"FCG-OLLAMA-{re.sub(r'[^A-Za-z0-9]', '', host)[:14]}-{re.sub(r'[^A-Za-z0-9]', '', model)[:14]}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
        run = run_session(model, sid, dict(os.environ))
        rec = {"model": model, "sid": sid, "rc": run["rc"], "seed_resolution": kv(run["out"], "SEED_RESOLUTION"), "err": run["err"] if run["rc"] else ""}
        if run["rc"] == 0:
            rec["v"] = verify_session(F, L, sid)
        sessions.append(rec)
        if run["rc"] != 0:
            break
    p = sessions[0]
    if "v" not in p:
        R["BLOCKED"] = f"Doctor3 exited {p['rc']}: {p['err'][:200]}"; print_report(R); return 2
    v = p["v"]; r = v["receipt"]
    R.update(SEED_RESOLUTION=p["seed_resolution"], SOURCE_PIN=r["source_pin"], VITHIA_PREPROCESSING=r["vithia_preprocessing"], PRE_EXEC_BP=r["pre_exec_breakpoint"],
             PRE_EXEC_MMR_ROOT=r["pre_exec_mmr_root"], PRE_EXEC_VERIFY=r["pre_exec_verify"], OPERATOR_IDENTITY_MODE=r["operator_identity_mode"],
             PUBLIC_KEY_FINGERPRINT=r["operator_public_key_fingerprint"], PRIVATE_KEY_MODE=v["key_mode"], PRIVATE_KEY_COMMITTED=v["key_committed"], PRIVATE_KEY_IN_FCO=v["key_in_fco"],
             MITOSIS_AUTH=r["mitosis_auth"], MITOSIS_EXACT_RETRIEVAL=r["mitosis_exact_retrieval"], TENKI_AUTH=r["tenki_auth"], TENKI_ARTIFACT_VERIFY=r["tenki_artifact_verify"],
             TENKI_ENVIRONMENT_REPLAY=r["tenki_environment_replay"], HOSTED_JEV="NOT_EXECUTED", DECIDER=r["decider"], DECISION_PROVIDER=v["decision"]["provider"],
             DECISION_ACTION=v["decision"]["selected_action"], DECISION_STATUS=v["decision"]["status"], DECISION_CEILING_FROM_CONTEXT=v["ceiling"],
             DECISION_SUPPORTED_BY_CONTEXT=v["supported"], DECISION_FCO_SHA256=v["decision_sha"], ACTION_EXECUTION_FCO_SHA256=v["action_sha"], OUTCOME_FCO_SHA256=v["outcome_sha"],
             ACTION_EXECUTION_STATUS=v["action_status"], OUTCOME_STATUS=v["outcome_status"], FINAL_FCG_BP=r["final_fcg_breakpoint"], FINAL_FCG_ROOT=r["final_fcg_mmr_root"],
             FINAL_MMR_SIZE=v["mmr_size"], PARENT_CHAIN_VERIFY=v["chain"], FINAL_FCG_BP_VERIFY=v["final_bp_verify"], CHECKPOINT_SIGNATURE_STATE=r["checkpoint_signature_state"],
             CHECKPOINT_SIGNATURE_VERIFY=v["sig_verify"], SECRET_SCAN=("PASS" if (v["scan"] == "PASS" and sh(sys.executable, "scripts/secret_scan.py").returncode == 0) else "FAIL"))
    R["OLLAMA_DECIDER"] = "PASS" if (v["decision"]["status"] == "PASS" and r["decider"] == "OLLAMA" and p["model"] in v["decision"]["provider"]) else "FAIL"
    R["DECISION_FCO"] = "PASS" if v["decision"]["status"] == "PASS" else v["decision"]["status"]
    R["ACTION_EXECUTION_FCO"] = "PASS" if v["action_status"] == "PASS" else v["action_status"]
    R["OUTCOME_FCO"] = "PASS" if v["outcome_status"] == "PASS" else v["outcome_status"]
    need = [R["OLLAMA_DECIDER"] == "PASS", R["DECISION_FCO"] == "PASS", R["ACTION_EXECUTION_FCO"] == "PASS", R["OUTCOME_FCO"] == "PASS", R["PARENT_CHAIN_VERIFY"] == "PASS",
            R["FINAL_FCG_BP_VERIFY"] == "PASS", R["CHECKPOINT_SIGNATURE_VERIFY"] == "PASS", R["SECRET_SCAN"] == "PASS", R["PRE_EXEC_VERIFY"] == "PASS",
            R["PRIVATE_KEY_MODE"] == "600", R["PRIVATE_KEY_COMMITTED"] == "NO", R["PRIVATE_KEY_IN_FCO"] == "NO", R["SEED_ROOT_MATCH"] == "PASS", R["SOURCE_PIN"] == "PASS"]
    same_host = a.previous_host.lower() in host.lower() or a.previous_host.lower() in socket.gethostname().lower()
    R["INVARIANTS_MATCH_PREVIOUS_RUN"] = {"seed_root": R["SEED_ROOT"] == EXPECTED_SEED_ROOT, "source_commit": R["SOURCE_COMMIT"] == EXPECTED_SOURCE, "final_root_may_differ": True}
    R["DOCTOR3_CROSS_MACHINE_PORTABILITY"] = ("PASS_BOUNDED" if (all(need) and not same_host) else
                                             ("NOT_ESTABLISHED_SAME_HOST_AS_PREVIOUS_RUN (all other checks: " + ("PASS" if all(need) else "FAIL") + ")" if same_host else "FAIL"))
    R["SECOND_MODEL_SESSIONS"] = [{"model": s["model"], "session": s["sid"], "action": s["v"]["decision"]["selected_action"] if "v" in s else None,
                                   "latency_ms": s["v"]["decision"]["decision_latency_ms"] if "v" in s else None, "provider": s["v"]["decision"]["provider"] if "v" in s else None,
                                   "supported_by_context": s["v"]["supported"] if "v" in s else None, "final_root": s["v"]["receipt"]["final_fcg_mmr_root"] if "v" in s else None,
                                   "exit_code": s["rc"]} for s in sessions]
    # --- commit only our report (doctor3 already pushed the sessions)
    rep = ROOT / "evidence/fcg_sessions" / p["sid"] / "PORTABILITY_VERIFICATION_REPORT.json"
    L.scan_text(json.dumps(R), "portability report")
    rep.write_text(json.dumps(R, indent=2, sort_keys=True) + "\n")
    R["COMMIT"] = R["PUSH"] = "NOT_ATTEMPTED"
    if not a.no_push:
        sh("git", "add", "--", str(rep.relative_to(ROOT)))
        c = sh("git", "commit", "-q", "-m", f"evidence: doctor3 local-ollama portability report ({p['sid']})")
        R["COMMIT"] = sh("git", "rev-parse", "HEAD").stdout.strip() if c.returncode == 0 else f"FAILED:{c.stderr.strip()[:100]}"
        pu = sh("git", "push", "-q", "origin", a.expected_branch); sh("git", "fetch", "origin")
        R["PUSH"] = "PASS" if pu.returncode == 0 else f"FAILED:{pu.stderr.strip()[:100]}"
        R["FINAL_ORIGIN_PARITY"] = "PASS" if sh("git", "rev-parse", "HEAD").stdout == sh("git", "rev-parse", f"origin/{a.expected_branch}").stdout else "FAIL"
    print_report(R)
    return 0 if all(need) else 1


def print_report(R: dict) -> None:
    order = ["HOST", "BRANCH", "HEAD", "ORIGIN_HEAD", "ORIGIN_PARITY", "WORKTREE", "SEED_ROOT", "SEED_FCO_VERIFY", "SEED_ROOT_MATCH", "SEED_RESOLUTION", "SOURCE_COMMIT", "SOURCE_PIN",
             "OLLAMA_BINARY", "OLLAMA_VERSION", "OLLAMA_SERVER", "OLLAMA_MODELS_AVAILABLE", "OLLAMA_MODEL", "OLLAMA_MODEL_ACTUAL", "OLLAMA_LOCAL_ONLY", "OLLAMA_DIRECT_SMOKE",
             "OLLAMA_ADAPTER_WIRING", "OLLAMA_ADAPTER_WIRING_DETAIL", "OPERATOR_IDENTITY_MODE", "PUBLIC_KEY_FINGERPRINT", "PRIVATE_KEY_MODE", "PRIVATE_KEY_COMMITTED", "PRIVATE_KEY_IN_FCO",
             "MITOSIS_AUTH", "MITOSIS_EXACT_RETRIEVAL", "TENKI_AUTH", "TENKI_ARTIFACT_VERIFY", "TENKI_ENVIRONMENT_REPLAY", "HOSTED_JEV", "VITHIA_PREPROCESSING", "PRE_EXEC_BP",
             "PRE_EXEC_MMR_ROOT", "PRE_EXEC_VERIFY", "DECIDER", "DECISION_PROVIDER", "OLLAMA_DECIDER", "DECISION_ACTION", "DECISION_STATUS", "DECISION_CEILING_FROM_CONTEXT",
             "DECISION_SUPPORTED_BY_CONTEXT", "DECISION_FCO", "DECISION_FCO_SHA256", "ACTION_EXECUTION_FCO", "ACTION_EXECUTION_FCO_SHA256", "OUTCOME_FCO", "OUTCOME_FCO_SHA256",
             "FINAL_FCG_BP", "FINAL_FCG_ROOT", "FINAL_MMR_SIZE", "PARENT_CHAIN_VERIFY", "FINAL_FCG_BP_VERIFY", "CHECKPOINT_SIGNATURE_STATE", "CHECKPOINT_SIGNATURE_VERIFY", "SECRET_SCAN",
             "PROMPT_PROFILE", "LANES_REQUESTED", "LANE_PRECHECKS", "CONTEXT_CEILING", "VERIFIED_CONTEXT_ROOT", "SAME_INPUT_CONTEXT_ROOT_ACROSS_LANES", "LANES", "LANES_CLAIM_GATE_INTEGRITY", "NOTE", "INVARIANTS_MATCH_PREVIOUS_RUN", "SECOND_MODEL_SESSIONS", "DOCTOR3_CROSS_MACHINE_PORTABILITY", "COMMIT", "PUSH", "FINAL_ORIGIN_PARITY", "BLOCKED"]
    for k in order:
        if k in R:
            v = R[k]
            print(f"{k}={json.dumps(v) if isinstance(v, (dict, list)) else v}")
    if "BLOCKED" not in R:
        print("BLOCKED=none")


if __name__ == "__main__":
    raise SystemExit(main())
