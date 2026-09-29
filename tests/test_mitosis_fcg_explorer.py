from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_explorer():
    spec = importlib.util.spec_from_file_location(
        "mitosis_fcg_explorer", ROOT / "tools/mitosis_fcg_explorer.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def test_graph_plan_covers_all_three_breakpoints():
    m = load_explorer()
    plan = m.graph_plan()
    bps = [n for n in plan["nodes"] if n["node_class"] == "breakpoint"]
    assert [n["breakpoint_id"] for n in bps] == [
        "VITHIA-E2E-POSTSUBMISSION-BP-0001",
        "VITHIA-E2E-POSTSUBMISSION-BP-0002",
        "VITHIA-E2E-POSTSUBMISSION-BP-0003",
    ]
    assert bps[-1]["mmr_root"] == plan["final_fcg_mmr_root"]


def test_every_breakpoint_depends_on_its_admitted_atoms():
    m = load_explorer()
    plan = m.graph_plan()
    for bp in [n for n in plan["nodes"] if n["node_class"] == "breakpoint"]:
        local = m.load_json(ROOT / bp["repo_path"])
        admitted = {"atom:" + a["sha256"] for a in local["atoms"]}
        assert admitted.issubset(set(bp["depends_on"]))


def test_node_text_is_secret_scannable_and_stable():
    m = load_explorer()
    plan = m.graph_plan()
    for node in plan["nodes"]:
        text = m.node_text(node, plan["session_id"])
        assert "VITHIA_FCG_GRAPH_NODE_V1" in text
        assert "MI_API_KEY" not in text
        assert "TENKI_API_KEY" not in text


def test_aliases_resolve_final_root_and_breakpoint():
    m = load_explorer()
    plan = m.graph_plan()
    aliases = plan["aliases"]
    final_key = aliases[plan["final_fcg_mmr_root"]]
    assert final_key == "bp:VITHIA-E2E-POSTSUBMISSION-BP-0003"
    assert aliases["VITHIA-E2E-POSTSUBMISSION-BP-0003"] == final_key


def test_mitosis_anchor_nodes_reference_existing_universal_ids():
    m = load_explorer()
    plan = m.graph_plan()
    anchors = [
        n for n in plan["nodes"]
        if n["kind"] in {"MitosisMemoryAnchorFCO", "MitosisVerificationAnchorFCO"}
    ]
    assert len(anchors) == 2
    assert all(n["external_source_uids"] for n in anchors)
    assert all(":" in n["external_source_uids"][0] for n in anchors)


def test_topological_order_places_dependencies_first():
    m = load_explorer()
    plan = m.graph_plan()
    ordered = m.topo_order(plan)
    pos = {n["key"]: i for i, n in enumerate(ordered)}
    for node in ordered:
        for dep in node.get("depends_on", []):
            assert pos[dep] < pos[node["key"]]
