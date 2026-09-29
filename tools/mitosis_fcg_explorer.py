#!/usr/bin/env python3
"""Materialize and probe the executed Vithia E2E lineage in Mitosis Cortex.

The graph is a projection of immutable local evidence:
- Mitosis universal_id = graph address
- FCO/receipt SHA-256 = immutable evidence identity
- Merkle/MMR root = checkpoint commitment

No credential value is written into graph text or repository evidence.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import vithia_e2e_lib as L  # noqa: E402

E2E = ROOT / "evidence/post_submission/e2e"
GRAPH_DIR = ROOT / "evidence/post_submission/mitosis_graph"
GRAPH_INDEX = GRAPH_DIR / "MITOSIS_FCG_GRAPH_INDEX.json"
FINAL_RECEIPT = E2E / "VITHIA_MITOSIS_TENKI_E2E_FINAL_RECEIPT.json"
LEDGER = E2E / "E2E_MMR_LEDGER.json"
OFFICE = "b236ff3a-8250-4ac5-bda2-4fc35c43d35f"
DEFAULT_ENV = ROOT / "vithia-space-sponsors.env"
AGENT = "vithia-fcg-explorer-v01"

BP_FILES = [
    E2E / "PRE_TENKI_BREAKPOINT.json",
    E2E / "POST_TENKI_BREAKPOINT.json",
    E2E / "FINAL_FCG_BREAKPOINT.json",
]

SAFE_FIELD_ALLOWLIST = {
    "SeedCheckpointFCO": [
        "session_id", "submitted_source_commit", "submitted_playthrough_mmr_root",
        "parent_fcg_root",
    ],
    "VithiaPreprocessingFCO": [
        "session_id", "context_root", "predecessor_context_root",
    ],
    "MitosisMemoryAnchorFCO": [
        "session_id", "universal_id", "retrieval_status", "exact_id_match",
        "vithia_context_root",
    ],
    "TenkiClaimCorrectionFCO": [
        "corrected_artifact_reconstruction", "corrected_environment_replay",
    ],
    "LocalEnvironmentReplayReceipt": [
        "environment_replay", "first_mismatch_frame", "first_mismatch_kind",
        "rgb_hash_equality", "frame_root_equality", "final_mmr_equality",
    ],
    "TenkiVerificationFCO": [
        "session_id", "artifact_reconstruction", "environment_replay",
        "expected_mmr_root", "recomputed_mmr_root", "first_mismatch",
        "tenki_source_pin", "sandbox_termination",
    ],
    "MitosisVerificationAnchorFCO": [
        "session_id", "universal_id", "retrieval_status", "exact_id_match",
        "tenki_verification_fco_sha256",
    ],
    "VithiaVerifiedContextFCO": [
        "session_id", "context_root", "predecessor_context_root",
        "verification_status",
    ],
    "DecisionFCO": [
        "session_id", "decider_type", "provider", "input_context_root",
        "selected_action", "status",
    ],
    "DecisionFCOComparator": [
        "session_id", "decider_type", "provider", "input_context_root",
        "selected_action", "status",
    ],
    "ActionExecutionFCO": [
        "session_id", "decision_fco_sha256", "action", "executed", "status",
    ],
    "OutcomeFCO": [
        "session_id", "action_execution_fco_sha256", "outcome", "status",
    ],
    "LoadBearingReceipt": [
        "verdict", "mitosis_verification_universal_id",
        "decision_depends_on_retrieved_memory", "decision_with_memory",
        "decision_without_memory",
    ],
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical_write(path: Path, obj: Any) -> str:
    data = L.canonical(obj)
    L.scan_text(data.decode("utf-8"), where=str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return L.sha(data)


def flatten_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def safe_summary(kind: str, path: Path) -> dict[str, Any]:
    if path.suffix != ".json" or not path.exists():
        return {}
    try:
        obj = load_json(path)
    except Exception:
        return {}
    fields = SAFE_FIELD_ALLOWLIST.get(kind, [])
    return {k: obj[k] for k in fields if k in obj}


def node_text(node: dict[str, Any], session_id: str) -> str:
    lines = [
        "VITHIA_FCG_GRAPH_NODE_V1",
        f"session_id={session_id}",
        f"node_key={node['key']}",
        f"node_class={node['node_class']}",
        f"kind={node['kind']}",
    ]
    if node.get("repo_path"):
        lines.append(f"repo_path={node['repo_path']}")
    if node.get("sha256"):
        lines.append(f"sha256={node['sha256']}")
    if node.get("fmo_leaf"):
        lines.append(f"fmo_leaf={node['fmo_leaf']}")
    if node.get("breakpoint_id"):
        lines.append(f"breakpoint_id={node['breakpoint_id']}")
    if node.get("bp_root"):
        lines.append(f"bp_root={node['bp_root']}")
    if node.get("mmr_root"):
        lines.append(f"mmr_root={node['mmr_root']}")
    if node.get("mmr_size") is not None:
        lines.append(f"mmr_size={node['mmr_size']}")
    if node.get("parent_root"):
        lines.append(f"parent_root={node['parent_root']}")
    for k, v in sorted((node.get("summary") or {}).items()):
        lines.append(f"{k}={flatten_value(v)}")
    text = "\n".join(lines)
    L.scan_text(text, where=f"graph node {node['key']}")
    return text


def existing_anchor_uid(kind: str, path: Path) -> str | None:
    if kind not in {"MitosisMemoryAnchorFCO", "MitosisVerificationAnchorFCO"}:
        return None
    try:
        uid = load_json(path).get("universal_id")
    except Exception:
        return None
    return uid if isinstance(uid, str) and ":" in uid else None


def graph_plan() -> dict[str, Any]:
    final = load_json(FINAL_RECEIPT)
    ledger = load_json(LEDGER)
    entries = {e["bp_id"]: e for e in ledger["entries"]}
    session_id = final["session_id"]

    nodes: list[dict[str, Any]] = []
    key_by_sha: dict[str, str] = {}
    previous_bp_key: str | None = None

    for bp_file in BP_FILES:
        bp = load_json(bp_file)
        bp_id = bp["breakpoint_id"]
        ledger_entry = entries[bp_id]
        atom_keys: list[str] = []

        for atom in bp["atoms"]:
            key = f"atom:{atom['sha256']}"
            if key not in {n["key"] for n in nodes}:
                repo_path = atom["path"]
                local = ROOT / repo_path
                node = {
                    "key": key,
                    "node_class": "artifact",
                    "kind": atom["kind"],
                    "group": atom["group"],
                    "repo_path": repo_path,
                    "sha256": atom["sha256"],
                    "fmo_leaf": atom["fmo_leaf"],
                    "admitted_in": bp_id,
                    "summary": safe_summary(atom["kind"], local),
                    "depends_on": [],
                    "external_source_uids": [],
                }
                ext = existing_anchor_uid(atom["kind"], local)
                if ext:
                    node["external_source_uids"].append(ext)

                # Semantic dependencies inside the already-executed graph.
                if atom["kind"] == "VithiaPreprocessingFCO":
                    seed = next((n["key"] for n in nodes if n["kind"] == "SeedCheckpointFCO"), None)
                    if seed:
                        node["depends_on"].append(seed)
                elif atom["kind"] == "LocalEnvironmentReplayReceipt":
                    seed = next((n["key"] for n in nodes if n["kind"] == "SeedCheckpointFCO"), None)
                    if seed:
                        node["depends_on"].append(seed)
                elif atom["kind"] == "PNGEncodingInvestigation":
                    dep = next((n["key"] for n in nodes if n["kind"] == "LocalEnvironmentReplayReceipt"), None)
                    if dep:
                        node["depends_on"].append(dep)
                elif atom["kind"] == "MitosisMemoryAnchorFCO":
                    dep = next((n["key"] for n in nodes if n["kind"] == "VithiaPreprocessingFCO"), None)
                    if dep:
                        node["depends_on"].append(dep)
                elif atom["kind"] in {"TenkiVerificationFCO", "TenkiExecutionRawResult", "TenkiCodeReviewReceipt"}:
                    if previous_bp_key:
                        node["depends_on"].append(previous_bp_key)
                elif atom["kind"] == "MitosisVerificationAnchorFCO":
                    dep = next((n["key"] for n in nodes if n["kind"] == "TenkiVerificationFCO"), None)
                    if dep:
                        node["depends_on"].append(dep)
                elif atom["kind"] == "VithiaVerifiedContextFCO":
                    for dep_kind in ("MitosisVerificationAnchorFCO",):
                        dep = next((n["key"] for n in nodes if n["kind"] == dep_kind), None)
                        if dep:
                            node["depends_on"].append(dep)
                    if previous_bp_key:
                        node["depends_on"].append(previous_bp_key)
                elif atom["kind"] in {"DecisionFCO", "DecisionFCOComparator"}:
                    dep = next((n["key"] for n in nodes if n["kind"] == "VithiaVerifiedContextFCO"), None)
                    if dep:
                        node["depends_on"].append(dep)
                elif atom["kind"] == "ActionExecutionFCO":
                    dep = next((n["key"] for n in nodes if n["kind"] == "DecisionFCO"), None)
                    if dep:
                        node["depends_on"].append(dep)
                elif atom["kind"] == "OutcomeFCO":
                    dep = next((n["key"] for n in nodes if n["kind"] == "ActionExecutionFCO"), None)
                    if dep:
                        node["depends_on"].append(dep)
                elif atom["kind"] == "LoadBearingReceipt":
                    for dep_kind in ("MitosisVerificationAnchorFCO", "VithiaVerifiedContextFCO", "DecisionFCO"):
                        dep = next((n["key"] for n in nodes if n["kind"] == dep_kind), None)
                        if dep:
                            node["depends_on"].append(dep)
                elif previous_bp_key:
                    node["depends_on"].append(previous_bp_key)

                nodes.append(node)
                key_by_sha[atom["sha256"]] = key
            atom_keys.append(key)

        bp_key = f"bp:{bp_id}"
        bp_node = {
            "key": bp_key,
            "node_class": "breakpoint",
            "kind": "CheckpointFCOProjection",
            "breakpoint_id": bp_id,
            "repo_path": str(bp_file.relative_to(ROOT)),
            "sha256": ledger_entry["bp_file_sha256"],
            "bp_root": ledger_entry["bp_root"],
            "mmr_root": ledger_entry["mmr_root_after"],
            "mmr_size": ledger_entry["mmr_size"],
            "parent_root": ledger_entry["parent_root"],
            "summary": {
                "lineage_id": ledger["lineage_id"],
                "atom_count": len(bp["atoms"]),
                "root_kind": bp["root_kind"],
            },
            "depends_on": list(atom_keys) + ([previous_bp_key] if previous_bp_key else []),
            "external_source_uids": [],
        }
        nodes.append(bp_node)
        previous_bp_key = bp_key

    aliases: dict[str, str] = {}
    for node in nodes:
        for value in (
            node.get("key"), node.get("sha256"), node.get("fmo_leaf"),
            node.get("breakpoint_id"), node.get("bp_root"), node.get("mmr_root"),
        ):
            if isinstance(value, str) and value:
                aliases[value] = node["key"]

    return {
        "schema": "MITOSIS_FCG_GRAPH_PLAN_V1",
        "session_id": session_id,
        "office_id": OFFICE,
        "agent": AGENT,
        "lineage_id": ledger["lineage_id"],
        "parent_lineage_reference": ledger["parent_lineage_reference"],
        "final_fcg_mmr_root": final["final_fcg_mmr_root"],
        "nodes": nodes,
        "aliases": aliases,
    }


def topo_order(plan: dict[str, Any]) -> list[dict[str, Any]]:
    remaining = {n["key"]: n for n in plan["nodes"]}
    ordered: list[dict[str, Any]] = []
    done: set[str] = set()
    while remaining:
        progressed = False
        for key, node in list(remaining.items()):
            if all(dep in done for dep in node.get("depends_on", [])):
                ordered.append(node)
                done.add(key)
                del remaining[key]
                progressed = True
        if not progressed:
            raise RuntimeError(f"GRAPH_DEPENDENCY_CYCLE:{sorted(remaining)}")
    return ordered


def materialize(args: argparse.Namespace) -> int:
    plan = graph_plan()
    if args.dry_run:
        print(json.dumps(plan, indent=2, sort_keys=True))
        return 0

    env = L.load_private_env(Path(args.env_file))
    if not env.get("MI_API_KEY"):
        print("MI_API_KEY=NOT_SET")
        return 2

    m = L.Mitosis(OFFICE, env)
    auth = m.auth()
    print(f"MITOSIS_AUTH={auth['state']}")
    if auth["state"] != "PASS":
        return 3

    uids: dict[str, str] = {}
    records: list[dict[str, Any]] = []
    for node in topo_order(plan):
        sources = [uids[k] for k in node.get("depends_on", [])]
        sources.extend(node.get("external_source_uids", []))
        # Stable de-duplication.
        sources = list(dict.fromkeys(sources))
        text = node_text(node, plan["session_id"])
        result = m.remember_linked(
            text,
            sources=sources,
            kind="observation" if node["node_class"] == "artifact" else "task-outcome",
            confidence=1.0,
            agent=AGENT,
        )
        if result["state"] != "PASS":
            print(f"GRAPH_NODE_WRITE=FAIL NODE={node['key']}")
            return 4
        uid = result["universal_id"]
        exact = m.get(uid)
        if exact["state"] != "PASS":
            print(f"GRAPH_NODE_GET=FAIL NODE={node['key']} UID={uid}")
            return 5
        uids[node["key"]] = uid
        records.append({
            "key": node["key"],
            "node_class": node["node_class"],
            "kind": node["kind"],
            "repo_path": node.get("repo_path"),
            "sha256": node.get("sha256"),
            "breakpoint_id": node.get("breakpoint_id"),
            "bp_root": node.get("bp_root"),
            "mmr_root": node.get("mmr_root"),
            "universal_id": uid,
            "source_universal_ids": sources,
            "linked_sources": result.get("linked_sources"),
            "derived_from_edges": result.get("derived_from_edges"),
            "exact_get": "PASS",
        })
        print(f"GRAPH_NODE_WRITE=PASS NODE={node['key']} UID={uid}")

    final_key = plan["aliases"][plan["final_fcg_mmr_root"]]
    final_uid = uids[final_key]
    probe = m.ask_json(
        f"Find the Vithia FCG checkpoint with final MMR root {plan['final_fcg_mmr_root']} "
        f"and node key {final_key}."
    )
    result_ids = [
        r.get("universal_id") for r in probe.get("results", [])
        if isinstance(r, dict)
    ]
    exact_match = final_uid in result_ids

    index = {
        "schema": "MITOSIS_FCG_GRAPH_INDEX_V1",
        "session_id": plan["session_id"],
        "office_id": OFFICE,
        "agent": AGENT,
        "lineage_id": plan["lineage_id"],
        "final_fcg_mmr_root": plan["final_fcg_mmr_root"],
        "final_checkpoint_universal_id": final_uid,
        "nodes": records,
        "aliases": {
            alias: uids[key] for alias, key in plan["aliases"].items() if key in uids
        },
        "final_probe": {
            "state": probe.get("state"),
            "exact_id_match": "YES" if exact_match else "NO",
            "cited_graph_url": probe.get("cited_graph_url"),
            "result_universal_ids": result_ids,
        },
        "claim_ceiling": (
            "Interactive Mitosis graph projection of immutable FCO/MMR evidence. "
            "Universal IDs are addresses; FCO hashes and Merkle/MMR roots remain canonical integrity identities."
        ),
    }
    idx_sha = canonical_write(GRAPH_INDEX, index)
    print(f"MITOSIS_FCG_GRAPH_INDEX={GRAPH_INDEX.relative_to(ROOT)}")
    print(f"MITOSIS_FCG_GRAPH_INDEX_SHA256={idx_sha}")
    print(f"MITOSIS_FINAL_CHECKPOINT_UID={final_uid}")
    print(f"MITOSIS_GRAPH_PROBE_EXACT_ID_MATCH={'YES' if exact_match else 'NO'}")
    print(f"MITOSIS_CITED_GRAPH_URL={probe.get('cited_graph_url')}")
    return 0


def load_index() -> dict[str, Any]:
    if not GRAPH_INDEX.exists():
        raise SystemExit("MITOSIS_FCG_GRAPH_INDEX=NOT_MATERIALIZED")
    return load_json(GRAPH_INDEX)


def resolve_uid(index: dict[str, Any], token: str) -> str | None:
    if token.startswith("agent:") or token.startswith("agent_memory:"):
        return token
    return index.get("aliases", {}).get(token)


def probe(args: argparse.Namespace) -> int:
    index = load_index()
    token = args.token
    uid = resolve_uid(index, token)
    if not uid:
        print("PROBE_RESOLVE=FAIL")
        return 2

    env = L.load_private_env(Path(args.env_file))
    m = L.Mitosis(OFFICE, env)
    auth = m.auth()
    print(f"MITOSIS_AUTH={auth['state']}")
    if auth["state"] != "PASS":
        return 3
    exact = m.get(uid)
    print(f"PROBE_EXACT_GET={exact['state']}")
    if exact["state"] != "PASS":
        return 4

    q = m.ask_json(f"Find Vithia FCG evidence with universal id {uid} and identifier {token}.")
    result_ids = [r.get("universal_id") for r in q.get("results", []) if isinstance(r, dict)]
    print(f"PROBE_UNIVERSAL_ID={uid}")
    print(f"PROBE_QUERY_EXACT_ID_MATCH={'YES' if uid in result_ids else 'NO'}")
    print(f"PROBE_CITED_GRAPH_URL={q.get('cited_graph_url')}")
    return 0


def verify(args: argparse.Namespace) -> int:
    index = load_index()
    env = L.load_private_env(Path(args.env_file))
    m = L.Mitosis(OFFICE, env)
    auth = m.auth()
    print(f"MITOSIS_AUTH={auth['state']}")
    if auth["state"] != "PASS":
        return 3

    errors: list[str] = []
    for row in index["nodes"]:
        p = row.get("repo_path")
        if p and (ROOT / p).exists() and row.get("sha256"):
            observed = L.sha((ROOT / p).read_bytes())
            if observed != row["sha256"]:
                errors.append(f"LOCAL_HASH_MISMATCH:{row['key']}")
        if m.get(row["universal_id"])["state"] != "PASS":
            errors.append(f"MITOSIS_GET_FAIL:{row['key']}")

    lineage = L.verify_lineage()
    if any(r["verify_state"] != "PASS" for r in lineage):
        errors.append("LOCAL_E2E_LINEAGE_VERIFY_FAIL")
    if lineage[-1]["recomputed_root"] != index["final_fcg_mmr_root"]:
        errors.append("FINAL_MMR_ROOT_MISMATCH")

    print(f"GRAPH_NODES_CHECKED={len(index['nodes'])}")
    print(f"E2E_BREAKPOINTS_CHECKED={len(lineage)}")
    print(f"MITOSIS_FCG_GRAPH_VERIFY={'PASS' if not errors else 'FAIL'}")
    if errors:
        print("ERRORS=" + json.dumps(errors, separators=(",", ":")))
        return 5
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env-file", default=str(DEFAULT_ENV))
    sub = ap.add_subparsers(dest="command", required=True)

    pmat = sub.add_parser("materialize")
    pmat.add_argument("--dry-run", action="store_true")
    pmat.set_defaults(func=materialize)

    pprobe = sub.add_parser("probe")
    pprobe.add_argument("token", help="universal ID, FCO SHA-256, breakpoint ID/root, or MMR root")
    pprobe.set_defaults(func=probe)

    pver = sub.add_parser("verify")
    pver.set_defaults(func=verify)

    args = ap.parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
