#!/usr/bin/env python3
"""Vithia FCG doctor engine: seed -> verify -> identity -> Vithia -> Mitosis -> checkpoint -> Tenki -> Mitosis
-> Vithia verified context -> decider -> outcome -> final checkpoint.

Fail-closed on integrity failures (seed/object/pin/secret/parent/signature). Provider unavailability is recorded
as an honest state (BLOCKED / NOT_AVAILABLE / NOT_EXECUTED), never upgraded to PASS. Credentials arrive only via
the process environment (or a private file parsed in memory); they are never written to any artifact.
Mitosis universal_id = address; FCO SHA-256 = evidence identity; Merkle/MMR root = checkpoint commitment.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vithia_e2e_lib as L  # noqa: E402

L.SCHEMAS["VITHIA_SEED_CHECKPOINT_FCO_V1"] = {"schema", "seed_id", "source_commit", "parent_fcg_root", "expected_mmr_root",
                                              "objects", "resolvers", "verifiers", "required_capabilities", "optional_deciders"}
L.SCHEMAS["FinalCheckpointReferenceFCO_V1"] = {"schema", "session_id", "final_root", "checkpoint_id",
                                               "operator_public_key_fingerprint", "verification_status",
                                               "decision_fco_sha256", "outcome_fco_sha256", "created_utc"}
L.SCHEMAS["AtomFCO_V1"] = {"schema", "session_id", "path", "sha256", "bytes", "predecessor_root", "created_utc"}
L.SCHEMAS["WatchOccurrenceFCO_V1"] = {"schema", "session_id", "atom_fco_sha256", "mitosis_universal_id",
                                      "retrieval_status", "exact_id_match", "predecessor_root", "created_utc"}

ONTOLOGY = ["PUBLISH_CLAIM_REPLAY_COMPLETE", "PUBLISH_CLAIM_ARTIFACT_VERIFIED_ONLY", "WITHHOLD_ALL_TENKI_CLAIMS"]
SIG_DOMAIN = b"VITHIA_FCG_CHECKPOINT_ROOT_V1\0"
TIER = {ONTOLOGY[2]: 0, ONTOLOGY[1]: 1, ONTOLOGY[0]: 2}
# Frozen prompt profiles: identical text for EVERY lane (Ollama/JEV/OpenJEV). Hashed and recorded in each DecisionFCO.
# neutral_v1 reproduces the wording used in the first rehearsal (no tier rules stated); explicit_v1 states the rule.
PROMPT_PROFILES = {
    "neutral_v1": {"instructions": "Choose exactly one action.", "criteria": {a: a for a in ONTOLOGY}},
    "explicit_v1": {"instructions": ("Choose exactly one action. Rule: choose an action only if verification_status shows the evidence it claims as PASS; "
                                     "if artifact_reconstruction is not PASS choose WITHHOLD_ALL_TENKI_CLAIMS; claim replay only if environment_replay is PASS."),
                    "criteria": {ONTOLOGY[0]: "Claim that environment replay reproduced the submitted playthrough (requires environment_replay=PASS).",
                                 ONTOLOGY[1]: "Claim only artifact verification (requires artifact_reconstruction=PASS); no replay claim.",
                                 ONTOLOGY[2]: "Publish no Tenki verification claim."}},
}


def prompt_sha(profile: str) -> str:
    return L.sha(L.canonical(PROMPT_PROFILES[profile]))


def parse_lanes(spec: str) -> list[dict]:
    """'scripted,ollama:llama3.2:3b,ollama:hf.co/x:Q4,openjev' -> lanes; every lane sees the same verified context."""
    lanes, seen = [], set()
    for tok in [t.strip() for t in spec.split(",") if t.strip()]:
        kind, _, model = tok.partition(":")
        if kind not in ("scripted", "ollama", "openjev", "jev", "skip"):
            raise Stop(f"LANES=FAIL: unknown decider {kind!r}")
        name = re.sub(r"[^A-Za-z0-9_.-]", "_", tok)[:60]
        if name in seen:
            raise Stop(f"LANES=FAIL: duplicate lane {tok!r}")
        seen.add(name)
        lanes.append({"kind": kind, "model": model or None, "name": name})
    if not lanes:
        raise Stop("LANES=FAIL: no lanes given")
    return lanes


class Stop(Exception):
    """Integrity failure: the pipeline must not continue."""


# ---------------------------------------------------------------- seed
def load_seed(seed_fco: Path | None, seed_root: str | None, resolver_dirs=()) -> tuple[dict, str]:
    if seed_fco is not None:
        raw = Path(seed_fco).read_bytes()
    elif seed_root:
        want = seed_root.removeprefix("sha256:")
        raw = None
        for d in resolver_dirs:
            for f in sorted(Path(d).glob("*.json")):
                try:
                    if L.sha(L.canonical(json.loads(f.read_bytes()))) == want:
                        raw = f.read_bytes()
                        break
                except Exception:
                    continue
            if raw:
                break
        if raw is None:
            raise Stop("SEED_RESOLUTION=BLOCKED: no configured resolver returned canonical seed bytes for that root")
    else:
        raise Stop("SEED_RESOLUTION=BLOCKED: neither --seed-fco nor --seed-root given")
    obj = json.loads(raw)
    computed = L.sha(L.canonical(obj))
    if seed_root and computed != seed_root.removeprefix("sha256:"):
        raise Stop(f"SEED_FCO_VERIFY=FAIL: computed seed root {computed} != requested")
    if obj.get("schema") != "VITHIA_SEED_CHECKPOINT_FCO_V1":
        raise Stop("SEED_FCO_VERIFY=FAIL: wrong schema")
    missing = L.SCHEMAS["VITHIA_SEED_CHECKPOINT_FCO_V1"] - set(obj)
    if missing:
        raise Stop(f"SEED_FCO_VERIFY=FAIL: missing fields {sorted(missing)}")
    return obj, computed


def verify_source(seed: dict, source_dir: Path) -> None:
    head = subprocess.run(["git", "-C", str(source_dir), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    if head != seed["source_commit"]:
        raise Stop(f"SOURCE_PIN=FAIL: HEAD {head[:12]} != seed commit {seed['source_commit'][:12]}")
    for o in seed["objects"]:
        p = Path(source_dir) / o["path"]
        if not p.is_file():
            raise Stop(f"OBJECT_RESOLUTION=FAIL: missing {o['path']}")
        if L.sha(p.read_bytes()) != o["sha256"]:
            raise Stop(f"OBJECT_RESOLUTION=FAIL: hash mismatch {o['path']}")


# ---------------------------------------------------------------- identity / signatures
def _fp(pub) -> str:
    from cryptography.hazmat.primitives import serialization as S
    return hashlib.sha256(pub.public_bytes(S.Encoding.Raw, S.PublicFormat.Raw)).hexdigest()


def make_identity(mode: str, session_id: str, pub_pem: str | None = None, key_dir: Path | None = None) -> dict:
    """Private key never leaves key_dir (default ~/.vithia/identities, mode 600); only the public key is returned."""
    from cryptography.hazmat.primitives import serialization as S
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    if mode == "anonymous":
        return {"mode": "ANONYMOUS", "public_key": "NONE", "fingerprint": "ANONYMOUS", "priv": None}
    if mode in ("file", "paste"):
        if not pub_pem or "PRIVATE" in pub_pem:
            raise Stop("IDENTITY=FAIL: a PUBLIC key PEM is required (private key material refused)")
        pub = S.load_pem_public_key(pub_pem.encode())
        return {"mode": "PUBLIC_KEY_SUPPLIED", "public_key": pub_pem.strip() + "\n", "fingerprint": _fp(pub), "priv": None}
    if mode == "generate":
        d = Path(key_dir) if key_dir else Path.home() / ".vithia/identities"
        d.mkdir(parents=True, exist_ok=True)
        kp = d / f"{session_id}.ed25519.pem"
        if kp.exists():
            priv = S.load_pem_private_key(kp.read_bytes(), password=None)
        else:
            priv = Ed25519PrivateKey.generate()
            fd = os.open(kp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(priv.private_bytes(S.Encoding.PEM, S.PrivateFormat.PKCS8, S.NoEncryption()))
        pem = priv.public_key().public_bytes(S.Encoding.PEM, S.PublicFormat.SubjectPublicKeyInfo).decode()
        return {"mode": "GENERATED_LOCAL_ED25519", "public_key": pem, "fingerprint": _fp(priv.public_key()), "priv": priv}
    raise Stop(f"IDENTITY=FAIL: unknown mode {mode}")


def sign_root(priv, root_hex: str) -> str:
    return base64.b64encode(priv.sign(SIG_DOMAIN + root_hex.encode())).decode()


def verify_signature(fco: dict) -> bool:
    from cryptography.hazmat.primitives import serialization as S
    try:
        pub = S.load_pem_public_key(fco["public_key"].encode())
        if _fp(pub) != fco["public_key_fingerprint"]:
            return False
        pub.verify(base64.b64decode(fco["signature"]), SIG_DOMAIN + fco["root"].encode())
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- session lineage (own ledger; never touches others)
class Lineage:
    def __init__(self, root: Path, sdir: Path, lineage_id: str, parent_root: str):
        self.root, self.sdir, self.lineage_id, self.parent_root = root, sdir, lineage_id, parent_root
        self.ledger_path = sdir / "FCG_MMR_LEDGER.json"

    def _ledger(self) -> dict:
        if self.ledger_path.exists():
            return json.loads(self.ledger_path.read_bytes())
        return {"schema": "VITHIA_FCG_SESSION_LEDGER_V1", "lineage_id": self.lineage_id, "parent_root": self.parent_root, "entries": []}

    def _atom(self, rel: str, kind: str, group: str) -> dict:
        h, n = L.sha256_file(self.root / rel)
        return {"path": rel, "kind": kind, "group": group, "bytes": n, "sha256": h, "fmo_leaf": L.leaf(rel, n, h).hex()}

    def append(self, file_name: str, atoms_spec) -> dict:
        led = self._ledger(); seq = len(led["entries"])
        parent = led["entries"][-1]["mmr_root_after"] if seq else self.parent_root
        atoms = [self._atom(*a) for a in atoms_spec]
        groups: dict[str, list] = {}
        for a in atoms:
            groups.setdefault(a["group"], []).append((a["path"], bytes.fromhex(a["fmo_leaf"])))
        broot, group_roots = L.fmo_root(groups)
        bp_id = f"{self.lineage_id}-BP-{seq + 1:04d}"
        doc = {"schema": "VITHIA_FCG_BREAKPOINT_V1", "lineage_id": self.lineage_id, "seq": seq, "breakpoint_id": bp_id,
               "parent_root": parent, "atoms": atoms, "group_roots": group_roots, "bp_root": broot, "created_utc": L.utc()}
        L.scan_text(L.canonical(doc).decode(), f"breakpoint {file_name}")
        f = self.sdir / file_name
        f.write_bytes(L.canonical(doc))
        fsha, _ = L.sha256_file(f)
        lf = L.mmr_leaf(seq, bp_id, broot, fsha)
        leaves = [bytes.fromhex(e["mmr_leaf"]) for e in led["entries"]] + [lf]
        mroot, _ = L.mmr_root(leaves)
        entry = {"seq": seq, "bp_id": bp_id, "bp_file": str(f.relative_to(self.root)), "bp_file_sha256": fsha, "bp_root": broot,
                 "parent_root": parent, "mmr_leaf": lf.hex(), "mmr_size": len(leaves), "mmr_root_after": mroot}
        led["entries"].append(entry)
        L.scan_text(L.canonical(led).decode(), "ledger")
        self.ledger_path.write_bytes(L.canonical(led))
        return entry

    def verify(self, seed_parent_root: str) -> list[dict]:
        led = json.loads(self.ledger_path.read_bytes())
        rows, prev, leaves = [], seed_parent_root, []
        for e in led["entries"]:
            errs = []
            try:
                f = self.root / e["bp_file"]
                fsha, _ = L.sha256_file(f)
                doc = json.loads(f.read_bytes())
                if fsha != e["bp_file_sha256"]:
                    errs.append("BP_FILE_SHA_MISMATCH")
                groups: dict[str, list] = {}
                for a in doc["atoms"]:
                    h, n = L.sha256_file(self.root / a["path"])
                    if h != a["sha256"] or n != a["bytes"] or L.leaf(a["path"], n, h).hex() != a["fmo_leaf"]:
                        errs.append(f"ATOM_MISMATCH:{a['path']}")
                    groups.setdefault(a["group"], []).append((a["path"], bytes.fromhex(a["fmo_leaf"])))
                broot, _ = L.fmo_root(groups)
                if broot != doc["bp_root"] or broot != e["bp_root"]:
                    errs.append("BP_ROOT_MISMATCH")
                if doc["parent_root"] != prev or e["parent_root"] != prev:
                    errs.append("PARENT_MISMATCH")
                lf = L.mmr_leaf(e["seq"], e["bp_id"], broot, fsha)
                leaves.append(lf)
                root, _ = L.mmr_root(leaves)
                if lf.hex() != e["mmr_leaf"] or root != e["mmr_root_after"]:
                    errs.append("MMR_MISMATCH")
                prev = root
                recomputed = root
            except Exception as ex:  # noqa: BLE001
                errs.append(f"EXC:{type(ex).__name__}")
                recomputed = None
            rows.append({"bp_id": e["bp_id"], "recomputed_root": recomputed, "verify_state": "PASS" if not errs else "FAIL", "errors": errs})
        return rows


# ---------------------------------------------------------------- providers
class SimMitosis(L.Mitosis):
    """Deterministic in-memory stand-in for tests/dry-runs. Receipts made with it carry provider_mode=SIMULATED."""
    provider_mode = "SIMULATED"

    def __init__(self, office="sim", break_retrieval=False):
        self.office, self.available, self.mem, self.break_retrieval, self.n = office, True, {}, break_retrieval, 0

    def auth(self):
        return {"state": "PASS", "office_list": "PASS", "expected_office_present": "YES"}

    def remember(self, text):
        L.scan_text(text, "sim fact"); self.n += 1; uid = f"agent:memories:sim{self.n:04d}"; self.mem[uid] = text
        return {"state": "PASS", "universal_id": uid, "embedded": False}

    def exact_query(self, question, uid, tries=1):
        if self.break_retrieval:
            return {"state": "FAIL", "exact_id_match": "NO", "top_universal_id": "agent:memories:other"}
        return {"state": "PASS", "exact_id_match": "YES", "top_universal_id": uid, "rank": 1}

    def get(self, uid):
        return {"state": "PASS" if uid in self.mem else "FAIL", "text": self.mem.get(uid)}


class SimTenki:
    provider_mode = "SIMULATED"

    def __init__(self, replay="PASS", first_mismatch=None):
        self.replay, self.first_mismatch = replay, first_mismatch

    def auth(self):
        return {"state": "PASS", "basis": "simulated"}

    def execute(self, repo_url, commit, session, plan, expected_root):
        rec = {"environment_replay": self.replay, "first_mismatch_frame": (self.first_mismatch or {}).get("frame"),
               "first_mismatch_kind": (self.first_mismatch or {}).get("kind"),
               "replay_from_start": self.replay, "step_hash_equality": self.replay, "final_mmr_equality": "PASS"}
        return {"execution_locus": "SIMULATED", "sandbox_create": "PASS", "tenki_session_id": "SIMULATED-SESSION", "source_pin": "PASS",
                "observed_head": commit, "commands": [{"name": v["name"], "exit_code": 0, "stdout_tail": json.dumps({"recomputed_mmr_root": expected_root})} for v in plan["verifiers"]],
                "receipts": {"env_replay": rec}, "terminated": "PASS"}


class TenkiReal:
    provider_mode = "REAL"

    def __init__(self, key: str, py: str | None = None):
        self.key = key
        self.py = py or os.environ.get("VITHIA_TENKI_PY") or next((p for p in (str(Path.home() / ".vithia/tenki_venv/bin/python"), "/tmp/tenki_venv/bin/python") if Path(p).exists()), None)

    def _env(self):
        return {**os.environ, "TENKI_API_KEY": self.key}

    def auth(self):
        if not self.key:
            return {"state": "BLOCKED", "basis": "TENKI_API_KEY NOT_SET"}
        if not self.py:
            return {"state": "NOT_AVAILABLE", "basis": "no interpreter with the tenki SDK (see doctor3 --setup-tenki)"}
        print("$ TENKI_AUTH <redacted>", file=sys.stderr)
        p = subprocess.run([self.py, str(Path(L.ROOT) / "tools/tenki_auth_probe.py")], env=self._env(), capture_output=True, text=True)
        try:
            j = json.loads(p.stdout)
        except Exception:
            return {"state": "FAIL", "basis": "probe produced no JSON"}
        return {"state": j.get("TENKI_AUTH", "FAIL"), "basis": "Client.who_am_i() server response" if j.get("TENKI_AUTH") == "PASS" else j.get("error_class", "")}

    def execute(self, repo_url, commit, session, plan, expected_root):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            pf, of = Path(td) / "plan.json", Path(td) / "out.json"
            pf.write_text(json.dumps(plan))
            print("$ TENKI_EXECUTE <redacted>", file=sys.stderr)
            subprocess.run([self.py, str(Path(L.ROOT) / "tools/tenki_execute_seed.py"), repo_url, commit, session, str(of), str(pf)],
                           env=self._env(), capture_output=True, text=True, timeout=2400)
            return json.loads(of.read_text()) if of.exists() else {"sandbox_create": "FAIL", "tenki_session_id": None, "source_pin": "NOT_EXECUTED", "commands": [], "receipts": {}}


def tenki_review_state(pr: str | None, post: bool) -> dict:
    """Code review is NOT execution verification. Billing exhaustion is BLOCKED, never FAIL."""
    if not pr:
        return {"state": "NOT_EXECUTED", "reason": "no review PR given"}
    try:
        if post:
            subprocess.run(["gh", "pr", "comment", pr, "--body", "@tenki-reviewer Please review the current integration: credential boundaries, FCO immutability, "
                            "exact Mitosis retrieval, Merkle/MMR reconstruction, failure-state preservation, Tenki attribution, load-bearing claim gates."], check=True, capture_output=True)
        c = json.loads(subprocess.check_output(["gh", "pr", "view", pr, "--json", "comments"], text=True))["comments"]
        body = next((x["body"] for x in reversed(c) if x["author"]["login"] == "tenki-reviewer"), "")
    except Exception as e:  # noqa: BLE001
        return {"state": "NOT_AVAILABLE", "reason": type(e).__name__}
    if "Insufficient balance" in body:
        return {"state": "BLOCKED", "reason": "review credit exhausted (billing), not an implementation defect"}
    if "Review complete" in body:
        return {"state": "CHANGES_REQUESTED" if re.search(r"[1-9]\d* (high|medium|critical)", body) else "PASS", "reason": "review complete"}
    return {"state": "NOT_AVAILABLE", "reason": "review not complete"}


# ---------------------------------------------------------------- Vithia + deciders
def vithia_gate(retrieved_text: str | None) -> dict:
    if retrieved_text is None:
        return {"artifact_reconstruction": "NOT_ESTABLISHED", "environment_replay": "NOT_ESTABLISHED", "source": "no retrieved memory"}
    g = lambda k: (re.search(rf"{k}=([A-Z_]+)", retrieved_text) or [0, "NOT_ESTABLISHED"])[1]
    return {"artifact_reconstruction": g("artifact_reconstruction"), "environment_replay": g("environment_replay"), "source": "retrieved Mitosis memory"}


def policy_scripted(v: dict) -> str:
    if v["environment_replay"] == "PASS" and v["artifact_reconstruction"] == "PASS":
        return ONTOLOGY[0]
    return ONTOLOGY[1] if v["artifact_reconstruction"] == "PASS" else ONTOLOGY[2]


def openjev_token(env: dict) -> str:
    tf = Path.home() / ".openjev" / "token"
    return env.get("OPENJEV_TOKEN") or (tf.read_text().strip() if tf.exists() else "")


def run_decider(kind: str, status: dict, env: dict, profile: str = "neutral_v1") -> dict:
    """No silent fallback: an unavailable requested decider is BLOCKED, not replaced. Same frozen prompt for every lane."""
    t0 = time.perf_counter()
    prof = PROMPT_PROFILES[profile]
    meta = {"prompt_profile": profile, "prompt_sha256": prompt_sha(profile)}
    if kind == "skip":
        return {"status": "NOT_EXECUTED", "action": None, "provider": "none", "latency": 0.0, **meta}
    if kind == "scripted":
        a = policy_scripted(status)
        return {"status": "PASS", "action": a, "provider": "none", "latency": round((time.perf_counter() - t0) * 1000, 4), **meta}
    try:
        if kind == "ollama":
            model = env.get("OLLAMA_MODEL", "llama3.2:3b")
            actions = ONTOLOGY if all(k == v for k, v in prof["criteria"].items()) else prof["criteria"]
            content = prof["instructions"] + " Reply JSON {\"action\": <one of the list>}.\n" + json.dumps({"actions": actions, "verification_status": status})
            req = urllib.request.Request(env.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434") + "/api/chat", headers={"Content-Type": "application/json"},
                                         data=json.dumps({"model": model, "stream": False, "format": "json", "options": {"temperature": 0},
                                                          "messages": [{"role": "user", "content": content}]}).encode())
            cand = json.loads(json.loads(urllib.request.urlopen(req, timeout=180).read())["message"]["content"]).get("action")
            prov = "ollama:" + model
        elif kind in ("jev", "openjev"):
            if kind == "jev":
                if not env.get("TYPESAFE_API_KEY"):
                    return {"status": "BLOCKED", "action": None, "provider": "typesafe-jev", "latency": 0.0, "note": "TYPESAFE_API_KEY NOT_SET", **meta}
                base, headers = "https://api.typesafe.ai", {"Authorization": "Bearer " + env["TYPESAFE_API_KEY"]}
            else:
                base, headers = env.get("OPENJEV_BASE_URL", "http://127.0.0.1:8765"), {}
                tok = openjev_token(env)                       # local shim bearer token (~/.openjev/token); never logged or stored
                if tok:
                    headers["Authorization"] = "Bearer " + tok
            body = {"state": {"verification_status": status}, "model": "jev-latest" if kind == "jev" else "openjev",
                    "questions": {"action": {"type": "choice", "instructions": prof["instructions"], "criteria": prof["criteria"]}}}
            req = urllib.request.Request(base + "/v1/systemone", data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers}, method="POST")
            resp = json.loads(urllib.request.urlopen(req, timeout=180).read())
            cand = resp["answers"]["action"]["choice"]
            prov = ("typesafe-jev:" if kind == "jev" else "openjev-local:") + str(resp.get("model"))
        else:
            return {"status": "BLOCKED", "action": None, "provider": kind, "latency": 0.0, "note": "unknown decider", **meta}
    except Exception as e:  # noqa: BLE001
        code = getattr(e, "code", "")
        return {"status": "BLOCKED", "action": None, "provider": kind, "latency": 0.0, "note": f"{type(e).__name__}{':' + str(code) if code else ''}", **meta}
    lat = round((time.perf_counter() - t0) * 1000, 1)
    return {"status": "PASS" if cand in ONTOLOGY else "FAIL", "action": cand if cand in ONTOLOGY else None, "provider": prov, "latency": lat, **meta}


# ---------------------------------------------------------------- claim guard
TENKI_PASS_FIELDS = ("tenki_source_pin", "tenki_artifact_verify", "tenki_environment_replay")
STATE_FIELDS = ("seed_fco_verify", "source_pin", "object_resolution", "mitosis_auth", "tenki_auth", "vithia_preprocessing", "mitosis_exact_retrieval",
                "pre_exec_verify", "tenki_code_review", "tenki_source_pin", "tenki_artifact_verify", "tenki_environment_replay",
                "mitosis_verification_exact_retrieval", "checkpoint_signature_state", "secret_scan", "parent_chain_verify")


def guard_receipt(r: dict) -> None:
    """Refuse to admit a receipt that overstates: unknown states, NOT_EXECUTED->PASS, local-as-Tenki, universal_id-as-root."""
    for k, v in r.items():
        if k.endswith("_root") and isinstance(v, str) and v.startswith("agent:"):
            raise Stop(f"CLAIM_GUARD=FAIL: {k} holds a Mitosis universal_id (address), not a root")
    for k in STATE_FIELDS:
        if k in r and r[k] not in L.STATES | {"NOT_USED"}:
            raise Stop(f"CLAIM_GUARD=FAIL: {k}={r[k]!r} is not a recognised state (states are never normalised)")
    if any(r.get(k) == "PASS" for k in TENKI_PASS_FIELDS) and r.get("tenki_provider_mode") != "SIMULATED":
        if not r.get("tenki_session"):
            raise Stop("CLAIM_GUARD=FAIL: Tenki PASS without a Tenki session (NOT_EXECUTED cannot become PASS)")
        if r.get("tenki_execution_locus") != "TENKI_SANDBOX":
            raise Stop("CLAIM_GUARD=FAIL: Tenki PASS attributed to a non-Tenki execution locus")
    if r.get("portable_agent_memory_load_bearing") in ("PASS", "PASS_BOUNDED") and not r.get("load_bearing_consumption"):
        raise Stop("CLAIM_GUARD=FAIL: load-bearing claim without a recorded downstream consumption")


# ---------------------------------------------------------------- session
class Session:
    def __init__(self, root: Path, source_dir: Path, seed: dict, seed_root: str, session_id: str, mitosis, tenki, identity: dict,
                 decider: str = "scripted", env: dict | None = None, repo_url: str = "", review_pr: str | None = None, post_review: bool = False,
                 lanes: list | None = None, profile: str = "neutral_v1"):
        self.root, self.source_dir, self.seed, self.seed_root, self.sid = Path(root), Path(source_dir), seed, seed_root, session_id
        self.m, self.t, self.ident, self.decider, self.env = mitosis, tenki, identity, decider, env or {}
        self.lanes = lanes or [{"kind": decider, "model": None, "name": decider}]
        self.profile = profile
        self.repo_url, self.review_pr, self.post_review = repo_url, review_pr, post_review
        self.sdir = self.root / "evidence/fcg_sessions" / session_id
        self.sdir.mkdir(parents=True, exist_ok=True)
        self.lin = Lineage(self.root, self.sdir, f"VITHIA-FCG-{session_id}", seed["parent_fcg_root"])
        self.r: dict = {"schema": "VITHIA_DOCTOR_SESSION_RECEIPT_V1", "session_id": session_id, "seed_root": "sha256:" + seed_root,
                        "source_commit": seed["source_commit"], "operator_identity_mode": identity["mode"],
                        "operator_public_key_fingerprint": identity["fingerprint"],
                        "provider_mode": "SIMULATED" if "SIMULATED" in (getattr(mitosis, "provider_mode", ""), getattr(tenki, "provider_mode", "")) else "REAL",
                        "tenki_provider_mode": getattr(tenki, "provider_mode", "NONE")}
        self._mauth = self._tauth = None
        self.fco: dict[str, str] = {}

    def mauth(self) -> dict:
        if self._mauth is None:
            self._mauth = self.m.auth()
        return self._mauth

    def tauth(self) -> dict:
        if self._tauth is None:
            self._tauth = self.t.auth() if self.t else {"state": "NOT_AVAILABLE", "basis": "tenki adapter off"}
        return self._tauth

    def rel(self, name: str) -> str:
        return str((self.sdir / name).relative_to(self.root))

    def phase1(self) -> dict:
        verify_source(self.seed, self.source_dir)                       # Stop on failure
        self.r.update(seed_fco_verify="PASS", source_pin="PASS", object_resolution="PASS")
        (self.sdir / "SEED_CHECKPOINT_FCO.json").write_bytes(L.canonical(self.seed))
        self.fco["seed"] = L.sha(L.canonical(self.seed))
        self.fco["identity"] = L.write_fco(self.sdir / "OPERATOR_IDENTITY_FCO.json", {
            "schema": "OperatorIdentityFCO_V1", "session_id": self.sid, "public_key": self.ident["public_key"],
            "public_key_fingerprint": self.ident["fingerprint"], "identity_mode": self.ident["mode"],
            "external_identity_binding": "UNVERIFIED", "created_utc": L.utc()})
        auth = self.mauth()
        caps = {"mitosis": auth["state"], "tenki": self.tauth()["state"]}
        self.r.update(mitosis_auth=auth["state"], tenki_auth=caps["tenki"], tenki_auth_basis=self.tauth().get("basis"))
        selected = [{"id": "SeedCheckpointFCO", "sha256": self.fco["seed"], "verification_state": "PASS"},
                    {"id": "OperatorIdentityFCO", "sha256": self.fco["identity"], "verification_state": "PASS"}]
        selected += [{"id": o["path"], "sha256": o["sha256"], "verification_state": "PASS"} for o in self.seed["objects"]]
        rejected = [{"id": f"capability:{k}", "reason": f"{k} auth state {v}; not admissible as verified"} for k, v in caps.items() if v != "PASS"]
        ctx_root = L.merkle([L.hp_ctx(x["id"], x["sha256"], x["verification_state"]) for x in selected]).hex()
        self.ctx_root = ctx_root
        self.fco["pre"] = L.write_fco(self.sdir / "VITHIA_PREPROCESSING_FCO.json", {
            "schema": "VithiaPreprocessingFCO_V1", "session_id": self.sid, "input_fco_roots": {"seed_fco_sha256": self.fco["seed"], "parent_fcg_root": self.seed["parent_fcg_root"]},
            "selected_context": selected, "rejected_context": rejected, "anticube_state": "NOT_COMPUTED", "g_star": "NOT_COMPUTED", "delta_g_star": "NOT_COMPUTED",
            "context_root": ctx_root, "predecessor_context_root": "NOT_APPLICABLE_ORIGIN", "created_utc": L.utc()})
        self.r.update(vithia_preprocessing="PASS", vithia_context_root=ctx_root)
        uid, retr, exact = "NONE", "NOT_EXECUTED", "NO"
        if auth["state"] == "PASS":
            fact = (f"VITHIA_FCG {self.sid}: seed_root={self.seed_root}; source_commit={self.seed['source_commit']}; parent_fcg_root={self.seed['parent_fcg_root']}; "
                    f"vithia_context_root={ctx_root}; operator_public_key_fingerprint={self.ident['fingerprint']}. Universal id is an address, not a Merkle root.")
            rt = self.m.roundtrip(fact, f"What are the seed root and Vithia context root for {self.sid}?")
            ok = rt["write"]["state"] == rt["query"]["state"] == rt["get"]["state"] == "PASS"
            uid = rt["write"].get("universal_id") or "NONE"
            retr, exact = ("PASS" if ok else "FAIL"), rt["query"].get("exact_id_match", "NO")
        self.r.update(mitosis_initial_universal_id=uid, mitosis_exact_retrieval=retr)
        self.fco["anchor"] = L.write_fco(self.sdir / "MITOSIS_MEMORY_ANCHOR_FCO.json", {
            "schema": "MitosisMemoryAnchorFCO_V1", "session_id": self.sid, "universal_id": uid, "seed_fco_sha256": self.fco["seed"],
            "submitted_source_commit": self.seed["source_commit"], "vithia_context_root": ctx_root, "retrieval_status": retr, "exact_id_match": exact,
            "operator_public_key_fingerprint": self.ident["fingerprint"], "created_utc": L.utc()})
        self.r["mitosis_memory_anchor_root"] = self.fco["anchor"]
        e = self.lin.append("PRE_EXEC_BREAKPOINT.json", [(self.rel(n), k, "fco") for n, k in (
            ("SEED_CHECKPOINT_FCO.json", "SeedCheckpointFCO"), ("OPERATOR_IDENTITY_FCO.json", "OperatorIdentityFCO"),
            ("VITHIA_PREPROCESSING_FCO.json", "VithiaPreprocessingFCO"), ("MITOSIS_MEMORY_ANCHOR_FCO.json", "MitosisMemoryAnchorFCO"))])
        rows = self.lin.verify(self.seed["parent_fcg_root"])
        if rows[-1]["verify_state"] != "PASS":
            raise Stop("PRE_EXEC_BP_VERIFY=FAIL")
        self.pre_root = e["mmr_root_after"]
        self.r.update(pre_exec_breakpoint=e["bp_id"], pre_exec_mmr_root=e["mmr_root_after"], pre_exec_mmr_size=e["mmr_size"], pre_exec_verify="PASS")
        return {"pre_exec_bp": e["bp_id"], "pre_exec_mmr_root": e["mmr_root_after"], "mitosis_exact_retrieval": retr}

    def phase2(self, tenki_commit: str | None) -> dict:
        rv = tenki_review_state(self.review_pr, self.post_review)
        self.r["tenki_code_review"] = rv["state"]
        ts = {"execution_locus": "NOT_EXECUTED", "sandbox_create": "NOT_EXECUTED", "tenki_session_id": None, "source_pin": "NOT_EXECUTED", "commands": [], "receipts": {}}
        tenki_state = self.tauth()
        if tenki_state["state"] == "PASS" and tenki_commit:
            plan = {"setup": self.seed["resolvers"].get("tenki_setup", []), "verifiers": self.seed["verifiers"]}
            ts = self.t.execute(self.repo_url or self.seed["resolvers"].get("repository", ""), tenki_commit, self.sid, plan, self.seed["expected_mmr_root"])
        kinds = {v["name"]: v.get("kind") for v in self.seed["verifiers"]}
        replay_names = [n for n, k in kinds.items() if k == "replay"]
        artifact_names = [n for n, k in kinds.items() if k == "artifact"]
        er = (ts.get("receipts") or {}).get(replay_names[0], {}) if replay_names else {}
        recomputed = None
        for c in ts.get("commands", []):
            m = re.search(r'"recomputed_mmr_root":\s*"([0-9a-f]{64})"', c.get("stdout_tail", ""))
            if m:
                recomputed = m.group(1)
        ran = ts.get("sandbox_create") == "PASS"
        exits = {c["name"]: c["exit_code"] for c in ts.get("commands", [])}
        art_ok = (ran and ts.get("source_pin") == "PASS" and bool(artifact_names) and all(exits.get(n) == 0 for n in artifact_names)
                  and recomputed == self.seed["expected_mmr_root"])
        artifact = "PASS" if art_ok else ("FAIL" if ran else "NOT_EXECUTED")
        envr = er.get("environment_replay", "NOT_EXECUTED")
        locus = ts.get("execution_locus", "NOT_EXECUTED")
        self.fco["tenki"] = L.write_fco(self.sdir / "TENKI_VERIFICATION_FCO.json", {
            "schema": "TenkiVerificationFCO_V1", "session_id": self.sid, "execution_locus": locus, "pre_tenki_commit": tenki_commit or "NONE",
            "pre_tenki_mmr_root": self.pre_root, "tenki_auth": tenki_state["state"], "tenki_session_id": ts.get("tenki_session_id"),
            "tenki_code_review_state": rv["state"], "tenki_source_pin": ts.get("source_pin", "NOT_EXECUTED"), "artifact_reconstruction": artifact,
            "environment_replay": envr, "frames_checked": None, "expected_mmr_root": self.seed["expected_mmr_root"], "recomputed_mmr_root": recomputed,
            "first_mismatch": {"frame": er.get("first_mismatch_frame"), "kind": er.get("first_mismatch_kind")},
            "replay_from_start": er.get("replay_from_start", "NOT_EXECUTED"), "step_hash_equality": er.get("step_hash_equality", "NOT_EXECUTED"),
            "final_mmr_equality": er.get("final_mmr_equality", "NOT_EXECUTED"), "provider_mode": self.r["provider_mode"],
            "claim_ceiling": "Integrity/reconstruction relative to frozen objects only; artifact PASS does not imply environment replay PASS.", "created_utc": L.utc()})
        self.r.update(tenki_session=ts.get("tenki_session_id"), tenki_execution_locus=locus, tenki_source_pin=ts.get("source_pin", "NOT_EXECUTED"),
                      tenki_artifact_verify=artifact, tenki_environment_replay=envr, tenki_verification_fco_root=self.fco["tenki"],
                      tenki_first_mismatch={"frame": er.get("first_mismatch_frame"), "kind": er.get("first_mismatch_kind")})
        # Mitosis writeback of the (truthful) Tenki state
        uid2, retr2, exact2 = "NONE", "NOT_EXECUTED", "NO"
        if self.mauth()["state"] == "PASS":
            fact = (f"VITHIA_FCG {self.sid} TenkiVerificationFCO_sha256={self.fco['tenki']}; tenki_session_id={ts.get('tenki_session_id')}; pre_exec_mmr_root={self.pre_root}; "
                    f"artifact_reconstruction={artifact}; environment_replay={envr}; expected_mmr={self.seed['expected_mmr_root']}; recomputed_mmr={recomputed}.")
            rt = self.m.roundtrip(fact, f"What is the Tenki verification result and hash for {self.sid}?")
            ok = rt["write"]["state"] == rt["query"]["state"] == rt["get"]["state"] == "PASS"
            uid2, retr2, exact2 = rt["write"].get("universal_id") or "NONE", ("PASS" if ok else "FAIL"), rt["query"].get("exact_id_match", "NO")
        self.fco["vanchor"] = L.write_fco(self.sdir / "MITOSIS_VERIFICATION_ANCHOR_FCO.json", {
            "schema": "MitosisVerificationAnchorFCO_V1", "session_id": self.sid, "universal_id": uid2, "tenki_verification_fco_sha256": self.fco["tenki"],
            "pre_tenki_mmr_root": self.pre_root, "retrieval_status": retr2, "exact_id_match": exact2, "created_utc": L.utc()})
        self.r.update(mitosis_verification_universal_id=uid2, mitosis_verification_exact_retrieval=retr2)
        e2 = self.lin.append("POST_VERIFY_BREAKPOINT.json", [(self.rel("TENKI_VERIFICATION_FCO.json"), "TenkiVerificationFCO", "fco"),
                                                              (self.rel("MITOSIS_VERIFICATION_ANCHOR_FCO.json"), "MitosisVerificationAnchorFCO", "fco")])
        if self.lin.verify(self.seed["parent_fcg_root"])[-1]["verify_state"] != "PASS":
            raise Stop("POST_VERIFY_BP_VERIFY=FAIL")
        self.r.update(post_verify_breakpoint=e2["bp_id"], post_verify_mmr_root=e2["mmr_root_after"], post_verify_mmr_size=e2["mmr_size"])
        # Vithia verified context: status is read from the RETRIEVED memory
        text = None
        if retr2 == "PASS":
            g = self.m.get(uid2)
            text = g.get("text") if g["state"] == "PASS" and self.fco["tenki"] in (g.get("text") or "") else None
        status, counter = vithia_gate(text), vithia_gate(None)
        selected = [{"id": "TenkiVerificationFCO", "sha256": self.fco["tenki"], "verification_state": artifact if artifact in L.STATES else "UNKNOWN"},
                    {"id": "MitosisVerificationAnchorFCO", "sha256": self.fco["vanchor"], "verification_state": retr2}]
        vroot = L.merkle([L.hp_ctx(x["id"], x["sha256"], x["verification_state"]) for x in selected]).hex()
        self.fco["vctx"] = L.write_fco(self.sdir / "VITHIA_VERIFIED_CONTEXT_FCO.json", {
            "schema": "VithiaVerifiedContextFCO_V1", "session_id": self.sid, "selected_evidence": selected,
            "rejected_evidence": ([] if envr == "PASS" else [{"id": "EnvironmentReplayAsPass", "reason": f"environment_replay={envr}; may not be cited as replay PASS"}]),
            "verification_status": status, "context_root": vroot, "predecessor_context_root": self.ctx_root, "anticube_state": "NOT_COMPUTED",
            "g_star": "NOT_COMPUTED", "delta_g_star": "NOT_COMPUTED", "status_read_from": status["source"],
            "counterfactual_without_retrieved_memory": {"verification_status": counter}, "created_utc": L.utc()})
        self.r.update(verified_context_root=vroot)
        ceiling = policy_scripted(status)
        lane_recs = []
        for i, ln in enumerate(self.lanes):
            env_l = dict(self.env)
            if ln["model"]:
                env_l["OLLAMA_MODEL"] = ln["model"]
            d = run_decider(ln["kind"], status, env_l, self.profile)     # every lane gets the SAME verified context and frozen prompt
            sfx = "" if i == 0 else "__" + ln["name"]
            overreach = bool(d["action"]) and ((d["action"] == ONTOLOGY[0] and envr != "PASS") or (d["action"] != ONTOLOGY[2] and artifact != "PASS"))
            supported = "NOT_APPLICABLE" if not d["action"] else ("NO" if overreach else "YES")
            dsha = L.write_fco(self.sdir / f"DECISION_FCO{sfx}.json", {
                "schema": "DecisionFCO_V1", "session_id": self.sid, "decider_type": ln["kind"].upper(), "provider": d["provider"], "input_context_root": vroot,
                "action_ontology": ONTOLOGY, "selected_action": d["action"] or "NONE", "decision_latency_ms": d["latency"], "status": d["status"],
                "output_sha256": L.sha((d["action"] or "NONE").encode()), "note": d.get("note", ""), "lane": ln["name"], "prompt_profile": d["prompt_profile"],
                "prompt_sha256": d["prompt_sha256"], "context_ceiling": ceiling, "supported_by_context": supported, "created_utc": L.utc()})
            exe = d["status"] == "PASS" and not overreach
            asha = L.write_fco(self.sdir / f"ACTION_EXECUTION_FCO{sfx}.json", {
                "schema": "ActionExecutionFCO_V1", "session_id": self.sid, "decision_fco_sha256": dsha, "action": d["action"] or "NONE", "lane": ln["name"],
                "executed": exe, "status": "PASS" if exe else ("NOT_EXECUTED" if d["status"] != "PASS" else "BLOCKED"), "created_utc": L.utc()})
            osha = L.write_fco(self.sdir / f"OUTCOME_FCO{sfx}.json", {
                "schema": "OutcomeFCO_V1", "session_id": self.sid, "action_execution_fco_sha256": asha, "lane": ln["name"],
                "outcome": "CLAIM_OVERREACH_REFUSED" if overreach else ("CLAIM_WITHIN_VERIFIED_CEILING" if exe else "NO_ACTION"),
                "status": "PASS" if exe else ("BLOCKED" if overreach else "NOT_EXECUTED"), "created_utc": L.utc()})
            lane_recs.append({"lane": ln["name"], "kind": ln["kind"], "provider": d["provider"], "status": d["status"], "action": d["action"], "supported_by_context": supported,
                              "latency_ms": d["latency"], "executed": exe, "note": d.get("note", ""), "input_context_root": vroot,
                              "decision_fco_sha256": dsha, "action_execution_fco_sha256": asha, "outcome_fco_sha256": osha, "files_suffix": sfx})
            if i == 0:
                d0 = d; self.fco["decision"], self.fco["action"], self.fco["outcome"] = dsha, asha, osha
        d = d0
        consumed = bool(text) and d["status"] == "PASS" and d["action"] != policy_scripted(counter)
        lb = "PASS_BOUNDED" if consumed else "NOT_ESTABLISHED"
        (self.sdir / "LOAD_BEARING_RECEIPT.json").write_bytes(L.canonical({
            "schema": "E2E_LOAD_BEARING_RECEIPT_V1", "session_id": self.sid, "causal_edge": ["MitosisVerificationAnchorFCO", "VithiaVerifiedContextFCO", "DecisionFCO"],
            "decision_with_memory": d["action"], "decision_without_memory": policy_scripted(counter), "verdict": lb,
            "scope": "BOUNDED: verification tier admitted by the retrieved memory", "created_utc": L.utc()}))
        lane_atoms = [(self.rel(f"{b}{x['files_suffix']}.json"), k, "fco") for x in lane_recs for b, k in (
            ("DECISION_FCO", "DecisionFCO"), ("ACTION_EXECUTION_FCO", "ActionExecutionFCO"), ("OUTCOME_FCO", "OutcomeFCO"))]
        e3 = self.lin.append("FINAL_FCG_BREAKPOINT.json", [(self.rel("VITHIA_VERIFIED_CONTEXT_FCO.json"), "VithiaVerifiedContextFCO", "fco")] + lane_atoms
                             + [(self.rel("LOAD_BEARING_RECEIPT.json"), "LoadBearingReceipt", "receipt")])
        rows = self.lin.verify(self.seed["parent_fcg_root"])
        if any(x["verify_state"] != "PASS" for x in rows):
            raise Stop("FINAL_FCG_BP_VERIFY=FAIL")
        final_root = e3["mmr_root_after"]
        sigstate = "NOT_USED"
        if self.ident["priv"] is not None:
            sig = {"schema": "CheckpointSignatureFCO_V1", "root": final_root, "signature": sign_root(self.ident["priv"], final_root),
                   "public_key_fingerprint": self.ident["fingerprint"], "public_key": self.ident["public_key"], "session_id": self.sid, "created_utc": L.utc()}
            if not verify_signature(sig):
                raise Stop("SIGNATURE=FAIL: signature does not verify; refusing to admit")
            L.write_fco(self.sdir / "CHECKPOINT_SIGNATURE_FCO.json", sig)
            sigstate = "PASS"
        fuid = "NONE"
        if self.mauth()["state"] == "PASS":
            ref = {"schema": "FinalCheckpointReferenceFCO_V1", "session_id": self.sid, "final_root": final_root, "checkpoint_id": e3["bp_id"],
                   "operator_public_key_fingerprint": self.ident["fingerprint"], "verification_status": f"artifact={artifact};replay={envr}",
                   "decision_fco_sha256": self.fco["decision"], "outcome_fco_sha256": self.fco["outcome"], "created_utc": L.utc()}
            rt = self.m.roundtrip(f"VITHIA_FCG {self.sid} FINAL checkpoint_id={e3['bp_id']} final_root={final_root} verification=artifact:{artifact}/replay:{envr}; "
                                  f"decision_fco={self.fco['decision']}; outcome_fco={self.fco['outcome']}.", f"What is the final checkpoint root for {self.sid}?")
            if rt["write"]["state"] == rt["query"]["state"] == rt["get"]["state"] == "PASS":
                fuid = rt["write"]["universal_id"]
                ref["mitosis_universal_id_address"] = fuid
            L.write_fco(self.sdir / "FINAL_CHECKPOINT_REFERENCE_FCO.json", ref)
        dk = self.lanes[0]["kind"].upper()
        self.r.update(lanes=[{k: v for k, v in x.items() if k != "files_suffix"} for x in lane_recs], prompt_profile=self.profile, prompt_sha256=prompt_sha(self.profile),
                      input_context_root_shared=("YES" if len({x["input_context_root"] for x in lane_recs}) == 1 else "NO"), context_ceiling=ceiling,
                      decider=dk if d["status"] == "PASS" else f"{dk}:{d['status']}", decision_root=self.fco["decision"], action_root=self.fco["action"],
                      outcome_root=self.fco["outcome"], final_fcg_breakpoint=e3["bp_id"], final_fcg_mmr_root=final_root, final_fcg_mmr_size=e3["mmr_size"],
                      checkpoint_signature_state=sigstate, final_mitosis_universal_id=fuid, portable_agent_memory_load_bearing=lb,
                      load_bearing_consumption=({"consumed_in_decision": True} if consumed else None), parent_chain_verify="PASS",
                      claim_ceiling="Roots prove integrity/reconstruction of frozen objects only; not scientific correctness. Universal id is an address.")
        files = [str(p) for p in self.sdir.glob("*.json")]
        sc = L.scan_paths(files)
        self.r["secret_scan"] = sc["state"]
        if sc["state"] != "PASS":
            raise Stop(f"SECRET_SCAN=FAIL {sc['hits']}")
        guard_receipt(self.r)
        self.r["created_utc"] = L.utc()
        rb = L.canonical(self.r)
        L.scan_text(rb.decode(), "session receipt")
        (self.sdir / "VITHIA_DOCTOR_SESSION_RECEIPT.json").write_bytes(rb)
        self.r["receipt_sha256"] = L.sha(rb)
        return self.r


# ---------------------------------------------------------------- watch mode
def watch(sess_root: Path, sid: str, mitosis, watch_dir: Path, seed_parent_root: str, max_events: int = 1, poll: float = 2.0) -> list[dict]:
    """New file -> AtomFCO -> Mitosis persist -> occurrence FCO -> append MMR leaf. Never mutates prior atoms."""
    sdir = sess_root / "evidence/fcg_sessions" / sid / "watch"
    sdir.mkdir(parents=True, exist_ok=True)
    lin = Lineage(sess_root, sdir, f"VITHIA-FCG-WATCH-{sid}", seed_parent_root)
    seen, out, prev = {p.name for p in Path(watch_dir).iterdir()}, [], seed_parent_root
    while len(out) < max_events:
        for p in sorted(Path(watch_dir).iterdir()):
            if p.name in seen or not p.is_file():
                continue
            seen.add(p.name)
            n = len(out) + 1
            data = p.read_bytes()
            ah = L.write_fco(sdir / f"ATOM_{n:04d}.json", {"schema": "AtomFCO_V1", "session_id": sid, "path": p.name, "sha256": L.sha(data),
                                                           "bytes": len(data), "predecessor_root": prev, "created_utc": L.utc()})
            rt = mitosis.roundtrip(f"VITHIA_FCG_WATCH {sid} atom_fco_sha256={ah} predecessor_root={prev}.", f"What is atom {ah} in {sid}?") if mitosis.auth()["state"] == "PASS" else \
                {"write": {"state": "NOT_EXECUTED"}, "query": {"state": "NOT_EXECUTED"}, "get": {"state": "NOT_EXECUTED"}}
            ok = rt["write"]["state"] == rt["query"]["state"] == rt["get"]["state"] == "PASS"
            oh = L.write_fco(sdir / f"OCCURRENCE_{n:04d}.json", {"schema": "WatchOccurrenceFCO_V1", "session_id": sid, "atom_fco_sha256": ah,
                             "mitosis_universal_id": rt["write"].get("universal_id", "NONE"), "retrieval_status": "PASS" if ok else rt["query"]["state"],
                             "exact_id_match": rt["query"].get("exact_id_match", "NO"), "predecessor_root": prev, "created_utc": L.utc()})
            e = lin.append(f"WATCH_BP_{n:04d}.json", [(str((sdir / f"ATOM_{n:04d}.json").relative_to(sess_root)), "AtomFCO", "fco"),
                                                        (str((sdir / f"OCCURRENCE_{n:04d}.json").relative_to(sess_root)), "WatchOccurrenceFCO", "fco")])
            prev = e["mmr_root_after"]
            out.append({"atom_fco_sha256": ah, "occurrence_fco_sha256": oh, "mmr_root": prev})
            print(f"WATCH_ROOT={prev}", flush=True)
            if len(out) >= max_events:
                break
        else:
            time.sleep(poll)
    return out


# ---------------------------------------------------------------- CLI
def make_seed(out: Path) -> tuple[str, str]:
    """Seed for the submitted 240-frame playthrough (objects pinned at the submitted commit)."""
    F = "evidence/competition/final_execution"
    submitted = "4c943a92e84d0fb2cd3d01e4fdf15a10991eda71"
    objs = []
    for p in (f"{F}/PLAYTHROUGH_FCO.json", f"{F}/FINAL_1P_RUN_PREREG.json", f"{F}/frames/FRAME_BREAKPOINT_LEAVES.jsonl",
              f"{F}/frames/PLAYTHROUGH_MMR_CONSTRUCTION_RECEIPT.json", f"{F}/frames/PLAYTHROUGH_MMR_VERIFICATION_RECEIPT_V2.json",
              f"{F}/FRAME_CUSTODY_PUBLIC_KEY.pem", "governance/lineage/UFA_JEV_COMP_MMR_LEDGER.json"):
        blob = subprocess.check_output(["git", "show", f"{submitted}:{p}"], cwd=L.ROOT)
        objs.append({"path": p, "sha256": L.sha(blob), "bytes": len(blob)})
    tip = L.comp_ledger_tip()
    seed = {"schema": "VITHIA_SEED_CHECKPOINT_FCO_V1", "seed_id": "UFA_JEV_SUBMITTED_PLAYTHROUGH_240_V1", "source_commit": submitted,
            "parent_fcg_root": tip["mmr_root"], "expected_mmr_root": "e55a47a7f16064477c4f101a38a849391c2fbc9f6557c5244daf0406b36dbd74",
            "objects": objs,
            "resolvers": {"repository": "https://github.com/biobitworks/jev-space-invaders.git", "mitosis_office": "b236ff3a-8250-4ac5-bda2-4fc35c43d35f",
                          "tenki_setup": ["python3 -m venv .venv || (apt-get install -y -qq python3-venv >/dev/null 2>&1; python3 -m venv .venv)",
                                          ".venv/bin/pip install -q gymnasium==1.3.0 ale-py==0.12.1 numpy==2.5.3 pillow cryptography"]},
            "verifiers": [{"name": "playthrough_custody", "kind": "artifact", "cmd": "{PY} scripts/verify_final_playthrough_custody_v2.py evidence/competition/final_execution/frames"},
                          {"name": "competition_lineage", "kind": "artifact", "cmd": "{PY} scripts/verify_competition_lineage.py"},
                          {"name": "env_replay", "kind": "replay", "cmd": "{PY} scripts/verify_environment_replay_v1.py --receipt /tmp/env_replay.json --locus TENKI_SANDBOX",
                           "receipt_path": "/tmp/env_replay.json"}],
            "required_capabilities": ["git", "python3"], "optional_deciders": ["scripted", "ollama", "openjev", "jev"]}
    b = L.canonical(seed)
    L.scan_text(b.decode(), "seed")
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_bytes(b)
    return L.sha(b), L.sha(b)


def build_env(a) -> dict:
    env = dict(os.environ)
    if getattr(a, "env_file", None):
        env.update(L.load_private_env(Path(a.env_file)))
    L.register_secret_values(v for k, v in env.items() if k.endswith(("_API_KEY", "_TOKEN")) and v)
    return env


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    ms = sub.add_parser("make-seed"); ms.add_argument("--out", required=True)
    for name in ("phase1", "run"):
        p = sub.add_parser(name)
        p.add_argument("--seed-fco"); p.add_argument("--seed-root"); p.add_argument("--resolver-dir", action="append", default=[])
        p.add_argument("--source-dir", required=True); p.add_argument("--session-id", required=True)
        p.add_argument("--identity-mode", default="anonymous", choices=["generate", "file", "paste", "anonymous"])
        p.add_argument("--identity-pub-file"); p.add_argument("--env-file")
        p.add_argument("--mitosis", default="real", choices=["real", "sim", "off"]); p.add_argument("--tenki", default="real", choices=["real", "sim", "off"])
        p.add_argument("--decider", default="scripted", choices=["scripted", "ollama", "openjev", "jev", "skip"])
        p.add_argument("--deciders", help="comma-separated lanes, e.g. scripted,ollama:llama3.2:3b,openjev (all share one verified context)")
        p.add_argument("--prompt-profile", default="neutral_v1", choices=sorted(PROMPT_PROFILES))
        p.add_argument("--tenki-commit"); p.add_argument("--commit-hook", help="command that commits+pushes the session dir and prints the pushed commit sha"); p.add_argument("--review-pr"); p.add_argument("--post-review-comment", action="store_true")
    w = sub.add_parser("watch")
    w.add_argument("--session-id", required=True); w.add_argument("--watch-dir", required=True); w.add_argument("--parent-root", required=True)
    w.add_argument("--max-events", type=int, default=1); w.add_argument("--mitosis", default="real", choices=["real", "sim", "off"]); w.add_argument("--env-file")
    a = ap.parse_args()
    try:
        if a.cmd == "make-seed":
            h, _ = make_seed(Path(a.out)); print(f"SEED_FCO_SHA256={h}\nSEED_ROOT=sha256:{h}"); return 0
        env = build_env(a)
        office = "b236ff3a-8250-4ac5-bda2-4fc35c43d35f"
        mit = SimMitosis() if a.mitosis == "sim" else L.Mitosis(office, env)
        if a.mitosis == "off":
            mit = L.Mitosis(office, {})
        if a.cmd == "watch":
            watch(L.ROOT, a.session_id, mit, Path(a.watch_dir), a.parent_root, a.max_events); return 0
        seed, sroot = load_seed(Path(a.seed_fco) if a.seed_fco else None, a.seed_root, a.resolver_dir)
        print(f"SEED_SCHEMA={seed['schema']}\nSEED_RESOLUTION=PASS\nSEED_FCO_VERIFY=PASS\nSEED_ROOT=sha256:{sroot}")
        office = seed["resolvers"].get("mitosis_office", office)
        if a.mitosis == "real":
            mit = L.Mitosis(office, env)
        ten = SimTenki() if a.tenki == "sim" else (TenkiReal(env.get("TENKI_API_KEY", "")) if a.tenki == "real" else None)
        pub = Path(a.identity_pub_file).read_text() if a.identity_pub_file else None
        ident = make_identity(a.identity_mode, a.session_id, pub)
        lanes = parse_lanes(a.deciders) if a.deciders else None
        S = Session(L.ROOT, Path(a.source_dir), seed, sroot, a.session_id, mit, ten, ident, (lanes[0]["kind"] if lanes else a.decider), env, seed["resolvers"].get("repository", ""),
                    a.review_pr, a.post_review_comment, lanes=lanes, profile=a.prompt_profile)
        st = S.phase1()
        for k, v in st.items():
            print(f"{k.upper()}={v}")
        if a.cmd == "phase1":
            return 0
        commit = a.tenki_commit
        if a.commit_hook:
            import shlex
            commit = subprocess.check_output(shlex.split(a.commit_hook), cwd=L.ROOT, text=True).strip().splitlines()[-1]
            print(f"PRE_EXEC_COMMIT={commit}")
        elif a.tenki == "sim":
            commit = commit or "SIMULATED_COMMIT"
        st = S.phase2(commit)
        for k in ("mitosis_auth", "tenki_auth", "tenki_code_review", "tenki_session", "tenki_source_pin", "tenki_artifact_verify", "tenki_environment_replay", "decider",
                  "portable_agent_memory_load_bearing", "pre_exec_mmr_root", "post_verify_mmr_root", "final_fcg_mmr_root", "checkpoint_signature_state", "secret_scan", "receipt_sha256"):
            print(f"{k.upper()}={st.get(k)}")
        return 0
    except Stop as e:
        print(f"STOP={e}", file=sys.stderr); print("PIPELINE=STOPPED"); return 2


if __name__ == "__main__":
    raise SystemExit(main())
