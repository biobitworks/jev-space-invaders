"""Vithia E2E library: canonical FCOs, append-only lineage (FMO atoms -> breakpoint -> MMR),
independent verification, credential boundary, Mitosis adapter, secret scan.

Invariants (enforced in code, not prose):
  * FCO identity = SHA-256(canonical bytes); the file on disk IS the canonical bytes.
  * Mitosis universal_id is an address, never a root; roots are 64-hex only.
  * Stage states come from a closed vocabulary and are never normalised.
  * Provider PASS is only ever derived from a real provider round-trip result.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.fmo import fmo_root, hp, leaf, merkle, mmr_leaf, mmr_root, sha256_file  # noqa: E402

E2E_DIR = ROOT / "evidence/post_submission/e2e"
LINEAGE_ID = "VITHIA-E2E-POSTSUBMISSION"
LEDGER = E2E_DIR / "E2E_MMR_LEDGER.json"
COMP_LEDGER = ROOT / "governance/lineage/UFA_JEV_COMP_MMR_LEDGER.json"

STATES = {"PASS", "FAIL", "BLOCKED", "NOT_EXECUTED", "NOT_AVAILABLE", "NOT_COMPUTED", "NOT_ESTABLISHED",
          "NOT_APPLICABLE", "NOT_MATERIALIZED", "PASS_BOUNDED", "CHANGES_REQUESTED", "UNKNOWN", "PARTIAL",
          "YES", "NO"}
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def state(s: str) -> str:
    if s not in STATES:
        raise ValueError(f"unknown state {s!r}; states are never normalised")
    return s


def hp_ctx(item_id: str, item_sha: str, verification_state: str) -> bytes:
    return hp("VITHIA_CTX_V1", item_id, item_sha, verification_state)


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ---------------------------------------------------------------- FCO schemas
SCHEMAS: dict[str, set[str]] = {
    "SeedCheckpointFCO_V1": {"schema", "session_id", "submitted_source_commit", "submitted_playthrough_mmr_root",
                             "local_replay_receipt_hash", "parent_fcg_root", "objects", "verifiers",
                             "mitosis_office", "tenki_review_pr", "created_utc"},
    "OperatorIdentityFCO_V1": {"schema", "session_id", "public_key", "public_key_fingerprint", "identity_mode",
                               "external_identity_binding", "created_utc"},
    "VithiaPreprocessingFCO_V1": {"schema", "session_id", "input_fco_roots", "selected_context", "rejected_context",
                                  "anticube_state", "g_star", "delta_g_star", "context_root",
                                  "predecessor_context_root", "created_utc"},
    "MitosisMemoryAnchorFCO_V1": {"schema", "session_id", "universal_id", "seed_fco_sha256",
                                  "submitted_source_commit", "vithia_context_root", "retrieval_status",
                                  "exact_id_match", "created_utc"},
    "CheckpointFCO_V1": {"schema", "lineage_id", "seq", "breakpoint_id", "bp_root", "mmr_root_after",
                         "parent_root", "created_utc"},
    "TenkiVerificationFCO_V1": {"schema", "session_id", "execution_locus", "pre_tenki_commit", "pre_tenki_mmr_root",
                                "tenki_auth", "tenki_session_id", "tenki_code_review_state", "tenki_source_pin",
                                "artifact_reconstruction", "environment_replay", "frames_checked",
                                "expected_mmr_root", "recomputed_mmr_root", "first_mismatch", "claim_ceiling",
                                "created_utc"},
    "MitosisVerificationAnchorFCO_V1": {"schema", "session_id", "universal_id", "tenki_verification_fco_sha256",
                                        "pre_tenki_mmr_root", "retrieval_status", "exact_id_match", "created_utc"},
    "VithiaVerifiedContextFCO_V1": {"schema", "session_id", "selected_evidence", "rejected_evidence",
                                    "verification_status", "context_root", "predecessor_context_root",
                                    "anticube_state", "g_star", "delta_g_star", "created_utc"},
    "DecisionFCO_V1": {"schema", "session_id", "decider_type", "provider", "input_context_root",
                       "action_ontology", "selected_action", "decision_latency_ms", "status", "output_sha256",
                       "created_utc"},
    "ActionExecutionFCO_V1": {"schema", "session_id", "decision_fco_sha256", "action", "executed", "status",
                              "created_utc"},
    "OutcomeFCO_V1": {"schema", "session_id", "action_execution_fco_sha256", "outcome", "status", "created_utc"},
    "CheckpointSignatureFCO_V1": {"schema", "root", "signature", "public_key_fingerprint", "public_key",
                                  "session_id", "created_utc"},
    "TENKI_CLAIM_CORRECTION_FCO_V1": {"schema", "supersedes_path", "supersedes_sha256", "reason",
                                      "corrected_artifact_reconstruction", "corrected_environment_replay",
                                      "created_utc"},
}


def validate_fco(obj: dict) -> None:
    sch = obj.get("schema")
    if sch not in SCHEMAS:
        raise ValueError(f"unknown FCO schema {sch!r}")
    missing = SCHEMAS[sch] - set(obj)
    if missing:
        raise ValueError(f"{sch} missing fields {sorted(missing)}")
    for k, v in obj.items():
        if k.endswith("_root") and isinstance(v, str) and v.startswith("agent:"):
            raise ValueError(f"{sch}.{k}: a Mitosis universal_id is an address, not a Merkle/MMR root")


def write_fco(path: Path, obj: dict) -> str:
    validate_fco(obj)
    b = canonical(obj)
    scan_text(b.decode(), where=str(path))
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_bytes(b)
    return sha(b)


def read_fco(path: Path) -> tuple[dict, str]:
    b = Path(path).read_bytes()
    obj = json.loads(b)
    if canonical(obj) != b:
        raise ValueError(f"{path} is not canonical bytes")
    validate_fco(obj)
    return obj, sha(b)


# ---------------------------------------------------------------- secrets
SECRET_PATTERNS = [
    ("OPENAI_STYLE_KEY", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}")),
    ("AWS_ACCESS_KEY", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("BEARER_TOKEN", re.compile(r"Bearer\s+[A-Za-z0-9._~+/-]{12,}", re.I)),
    ("MI_TK_TOKEN", re.compile(r"\b(?:mi|tk)_[A-Za-z0-9_-]{12,}")),
    ("PRIVATE_KEY_PEM", re.compile(r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----")),
    ("SECRET_ASSIGNMENT", re.compile(
        r"\b(?:MI_API_KEY|MITOSIS_API_KEY|TENKI_API_KEY|TYPESAFE_API_KEY|ANTHROPIC_API_KEY|OPENAI_API_KEY|"
        r"AWS_ACCESS_KEY_ID|AWS_SECRET_ACCESS_KEY|AWS_SESSION_TOKEN)\s*[=:]\s*[\"']?[A-Za-z0-9/+_.-]{12,}")),
    ("EMAIL", re.compile(r"\b[\w.+-]+@(?!example\.com)[\w-]+\.[A-Za-z]{2,}\b")),
    ("PRIVATE_PATH", re.compile(r"/Users/[A-Za-z0-9_.-]+/")),
]
_SAMPLES = {  # assembled at runtime so no secret-shaped literal exists in source
    "OPENAI_STYLE_KEY": "sk" + "-abcdefghijklmnopqrst1", "AWS_ACCESS_KEY": "AK" + "IAABCDEFGHIJKLMNOP",
    "BEARER_TOKEN": "Bear" + "er abcdefghijkl1234", "MI_TK_TOKEN": "m" + "i_abcdefghij12",
    "PRIVATE_KEY_PEM": "-----BEGIN " + "PRIVATE KEY-----", "SECRET_ASSIGNMENT": "TENKI_API" + "_KEY=abcdefghijkl1",
    "EMAIL": "a" + "@b.io", "PRIVATE_PATH": "/Us" + "ers/x/"}
assert all(p.search(_SAMPLES[n]) for n, p in SECRET_PATTERNS), "secret pattern self-test failed"

_KNOWN_SECRET_VALUES: set[str] = set()


def register_secret_values(values) -> None:
    _KNOWN_SECRET_VALUES.update(v for v in values if v and len(v) >= 8)


def scan_text(text: str, where: str = "<text>") -> None:
    hits = [n for n, p in SECRET_PATTERNS if p.search(text)]
    hits += ["KNOWN_SECRET_VALUE" for v in _KNOWN_SECRET_VALUES if v in text]
    if hits:
        raise ValueError(f"SECRET_SCAN=FAIL {where}: {sorted(set(hits))}")


def scan_paths(paths) -> dict:
    hits = []
    for p in paths:
        p = Path(p)
        if not p.is_file() or p.suffix in {".png", ".mp4", ".pyc"}:
            continue
        try:
            t = p.read_text(errors="ignore")
        except Exception:
            continue
        for n, pat in SECRET_PATTERNS:
            if n in {"EMAIL", "PRIVATE_PATH"} and p.suffix == ".py":
                continue
            if pat.search(t):
                hits.append({"file": str(p.relative_to(ROOT)) if p.is_absolute() else str(p), "kind": n})
        for v in _KNOWN_SECRET_VALUES:
            if v in t:
                hits.append({"file": str(p), "kind": "KNOWN_SECRET_VALUE"})
    return {"state": "PASS" if not hits else "FAIL", "scanned": len(list(paths)), "hits": hits}


def load_private_env(path: Path) -> dict[str, str]:
    """Safe parser (no shell `source`). Returns values in memory only; callers must never print them."""
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:]
        k, v = line.split("=", 1)
        v = v.strip().strip("'\"")
        if v:
            env[k.strip()] = v
    register_secret_values(env.values())
    return env


# ---------------------------------------------------------------- lineage
def _atom(rel: str, kind: str, group: str) -> dict:
    p = ROOT / rel
    h, n = sha256_file(p)
    return {"path": rel, "kind": kind, "group": group, "bytes": n, "sha256": h,
            "fmo_leaf": leaf(rel, n, h).hex()}


def atoms_root(atoms: list[dict]) -> tuple[str, dict]:
    groups: dict[str, list] = {}
    for a in atoms:
        groups.setdefault(a["group"], []).append((a["path"], bytes.fromhex(a["fmo_leaf"])))
    return fmo_root(groups)


def comp_ledger_tip() -> dict:
    d = json.loads(COMP_LEDGER.read_text())
    leaves = [bytes.fromhex(e["mmr_leaf"]) for e in d["entries"]]
    recomputed, _ = mmr_root(leaves)
    tip = d["entries"][-1]
    if recomputed != tip["mmr_root_after"]:
        raise ValueError("competition ledger tip does not recompute; refusing to use it as parent")
    return {"lineage_id": d["lineage_id"], "bp_id": tip["bp_id"], "mmr_size": tip["mmr_size"],
            "mmr_root": recomputed}


def load_ledger() -> dict:
    if LEDGER.exists():
        return json.loads(LEDGER.read_text())
    return {"schema": "VITHIA_E2E_MMR_LEDGER_V1", "lineage_id": LINEAGE_ID, "protocol": "docs/BREAKPOINT_PROTOCOL.md",
            "parent_lineage_reference": comp_ledger_tip(), "entries": []}


def create_breakpoint(slug_file: str, atoms_spec: list[tuple[str, str, str]]) -> dict:
    """atoms_spec: [(repo-relative path, kind, group)]. Append-only; parent = previous MMR root or the
    verified competition tip (a cross-lineage REFERENCE; the competition ledger is never modified)."""
    ledger = load_ledger()
    seq = len(ledger["entries"])
    parent = ledger["entries"][-1]["mmr_root_after"] if seq else ledger["parent_lineage_reference"]["mmr_root"]
    atoms = [_atom(*a) for a in atoms_spec]
    broot, groups = atoms_root(atoms)
    bp_id = f"{LINEAGE_ID}-BP-{seq + 1:04d}"
    doc = {"schema": "VITHIA_E2E_BREAKPOINT_V1", "lineage_id": LINEAGE_ID, "seq": seq, "breakpoint_id": bp_id,
           "parent_root": parent, "root_kind": "FMO_V1_BREAKPOINT_ATOMS", "atoms": atoms,
           "group_roots": groups, "bp_root": broot, "created_utc": utc()}
    path = E2E_DIR / slug_file
    scan_text(canonical(doc).decode(), where=f"breakpoint {slug_file}")
    path.write_bytes(canonical(doc))
    fsha, _ = sha256_file(path)
    lf = mmr_leaf(seq, bp_id, broot, fsha)
    leaves = [bytes.fromhex(e["mmr_leaf"]) for e in ledger["entries"]] + [lf]
    root, peaks = mmr_root(leaves)
    entry = {"seq": seq, "bp_id": bp_id, "bp_file": str(path.relative_to(ROOT)), "bp_file_sha256": fsha,
             "bp_root": broot, "parent_root": parent, "mmr_leaf": lf.hex(), "mmr_size": len(leaves),
             "mmr_root_after": root, "mmr_peaks_after": peaks}
    ledger["entries"].append(entry)
    scan_text(canonical(ledger).decode(), where="ledger")
    LEDGER.write_bytes(canonical(ledger))
    return entry


def verify_lineage(upto_bp_id: str | None = None) -> list[dict]:
    """Recompute every hash from the files on disk; stored roots are never trusted."""
    ledger = json.loads(LEDGER.read_text())
    out, prev_root, leaves = [], comp_ledger_tip()["mmr_root"], []
    for e in ledger["entries"]:
        row = {"breakpoint_id": e["bp_id"], "lineage": LINEAGE_ID, "expected_root": e["mmr_root_after"],
               "parent_root": e["parent_root"], "mmr_size": e["mmr_size"], "file_hash": e["bp_file_sha256"],
               "recomputed_root": None, "verify_state": "FAIL", "errors": []}
        try:
            f = ROOT / e["bp_file"]
            fsha, _ = sha256_file(f)
            if fsha != e["bp_file_sha256"]:
                row["errors"].append("BP_FILE_SHA_MISMATCH")
            doc = json.loads(f.read_bytes())
            atoms = doc["atoms"]
            for a in atoms:
                h, n = sha256_file(ROOT / a["path"])
                if h != a["sha256"] or n != a["bytes"]:
                    row["errors"].append(f"ATOM_MISMATCH:{a['path']}")
                if leaf(a["path"], n, h).hex() != a["fmo_leaf"]:
                    row["errors"].append(f"LEAF_MISMATCH:{a['path']}")
            broot, _ = atoms_root(atoms)
            if broot != doc["bp_root"] or broot != e["bp_root"]:
                row["errors"].append("BP_ROOT_MISMATCH")
            if doc["parent_root"] != prev_root or e["parent_root"] != prev_root:
                row["errors"].append("PARENT_MISMATCH")
            lf = mmr_leaf(e["seq"], e["bp_id"], broot, fsha)
            if lf.hex() != e["mmr_leaf"]:
                row["errors"].append("MMR_LEAF_MISMATCH")
            leaves.append(lf)
            root, _ = mmr_root(leaves)
            row["recomputed_root"] = root
            if root != e["mmr_root_after"] or len(leaves) != e["mmr_size"]:
                row["errors"].append("MMR_ROOT_MISMATCH")
            prev_root = root
        except Exception as ex:  # noqa: BLE001
            row["errors"].append(f"EXC:{type(ex).__name__}:{ex}")
        row["verify_state"] = "PASS" if not row["errors"] else "FAIL"
        out.append(row)
        if upto_bp_id and e["bp_id"] == upto_bp_id:
            break
    return out


# ---------------------------------------------------------------- Mitosis (real round-trips only)
# Pinned: an unpinned @latest would run moving remote code in a process that holds the API key.
MI_SDK_SPEC = "@mitosislabs/sdk@0.27.2"


class Mitosis:
    """Drives the official `mi` CLI. The key travels only via the child's environment; argv/logs never
    carry it. PASS states are derived exclusively from real responses."""

    def __init__(self, office: str, env: dict[str, str]):
        self.office = office
        self.child_env = {**os.environ, "MI_API_KEY": env.get("MI_API_KEY", "")}
        self.available = bool(env.get("MI_API_KEY"))

    def _mi(self, *args: str, timeout: int = 120):
        cmd = ["npx", "-y", "-p", MI_SDK_SPEC, "mi", *args]
        print("$ MITOSIS_CLI", args[0], args[1] if len(args) > 1 else "", "<redacted-auth>", file=sys.stderr)
        p = subprocess.run(cmd, env=self.child_env, capture_output=True, text=True, timeout=timeout)
        try:
            return p.returncode, json.loads(p.stdout)
        except Exception:
            return p.returncode, {"_raw_len": len(p.stdout), "_err": p.stderr[-300:].replace(self.child_env["MI_API_KEY"], "<redacted>") if self.child_env["MI_API_KEY"] else p.stderr[-300:]}

    def auth(self) -> dict:
        if not self.available:
            return {"state": "BLOCKED", "reason": "MI_API_KEY NOT_SET"}
        rc, out = self._mi("offices", "list")
        ids = [o.get("id") for o in out] if isinstance(out, list) else []
        return {"state": "PASS" if (rc == 0 and ids) else "FAIL", "office_list": "PASS" if ids else "FAIL",
                "expected_office_present": "YES" if self.office in ids else "NO"}

    def get(self, uid: str) -> dict:
        rc, out = self._mi("cortex", "get", uid, "--office", self.office)
        ok = rc == 0 and out.get("universal_id") == uid
        return {"state": "PASS" if ok else "FAIL", "text": (out.get("raw_data") or {}).get("text") if ok else None}

    def remember(self, text: str) -> dict:
        scan_text(text, "mitosis fact")
        rc, out = self._mi("cortex", "remember", text, "--office", self.office, "--kind", "observation",
                           "--confidence", "1.0")
        uid = out.get("universal_id")
        return {"state": "PASS" if (rc == 0 and out.get("status") == "ok" and uid) else "FAIL",
                "universal_id": uid, "embedded": out.get("embedded")}

    def exact_query(self, question: str, uid: str, tries: int = 6) -> dict:
        """PASS only if the returned evidence list contains the EXACT universal_id (not nearest-neighbour)."""
        for _ in range(tries):
            rc, out = self._mi("cortex", "ask", question, "--office", self.office, "--json")
            ids = [r.get("universal_id") for r in out.get("results", [])] if isinstance(out, dict) else []
            if rc == 0 and uid in ids:
                return {"state": "PASS", "exact_id_match": "YES", "top_universal_id": ids[0], "rank": ids.index(uid) + 1}
            time.sleep(4)
        return {"state": "FAIL", "exact_id_match": "NO", "top_universal_id": (ids[0] if ids else None)}

    def roundtrip(self, text: str, question: str) -> dict:
        w = self.remember(text)
        if w["state"] != "PASS":
            return {"write": w, "query": {"state": "NOT_EXECUTED"}, "get": {"state": "NOT_EXECUTED"}}
        q = self.exact_query(question, w["universal_id"])
        g = self.get(w["universal_id"])
        g["text_matches"] = "YES" if g.get("text") == text else "NO"
        if g["state"] == "PASS" and g["text_matches"] != "YES":
            g["state"] = "FAIL"
        g.pop("text", None)
        return {"write": w, "query": q, "get": g}
