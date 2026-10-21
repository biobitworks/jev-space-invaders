import json, sys, importlib
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import vithia_e2e_lib as L
from src.fmo import mmr_leaf, mmr_root

def fco(schema, **kw):
    base = {f: "x" for f in L.SCHEMAS[schema]}
    base.update(kw, schema=schema)
    return base

def test_universal_id_is_not_a_root():
    with pytest.raises(ValueError, match="address, not a Merkle"):
        L.validate_fco(fco("CheckpointFCO_V1", bp_root="agent:memories:abc"))

def test_missing_field_and_unknown_schema():
    o = fco("OutcomeFCO_V1"); o.pop("outcome")
    with pytest.raises(ValueError, match="missing"): L.validate_fco(o)
    with pytest.raises(ValueError, match="unknown FCO schema"): L.validate_fco({"schema": "Nope"})

def test_states_never_normalised():
    assert L.state("NOT_EXECUTED") == "NOT_EXECUTED"
    for bad in ("OK", "pass", "SKIPPED", ""):
        with pytest.raises(ValueError): L.state(bad)

@pytest.mark.parametrize("text", ["MI_API" + "_KEY=abcdefghijklmnop", "Bear" + "er abcdefghijklmnopqr",
    "-----BEGIN " + "PRIVATE KEY-----", "AK" + "IAABCDEFGHIJKLMNOP", "x" + "@corp.io", "/Us" + "ers/someone/secret"])
def test_secret_scan_hard_fails(text):
    with pytest.raises(ValueError, match="SECRET_SCAN=FAIL"): L.scan_text(text)

def test_known_secret_value_in_fco_fails(tmp_path):
    L.register_secret_values({"s3cr3t-value-123456"})
    o = fco("OutcomeFCO_V1", outcome="contains s3cr3t-value-123456")
    with pytest.raises(ValueError, match="KNOWN_SECRET_VALUE"): L.write_fco(tmp_path / "o.json", o)
    L._KNOWN_SECRET_VALUES.clear()

def test_non_canonical_fco_rejected(tmp_path):
    p = tmp_path / "o.json"; p.write_text(json.dumps(fco("OutcomeFCO_V1"), indent=2))
    with pytest.raises(ValueError, match="not canonical"): L.read_fco(p)

@pytest.fixture
def lineage(tmp_path, monkeypatch):
    (tmp_path / "e2e").mkdir()
    leaf0 = mmr_leaf(0, "C-0", "aa" * 32, "bb" * 32)
    root0, _ = mmr_root([leaf0])
    comp = tmp_path / "comp.json"
    comp.write_text(json.dumps({"lineage_id": "C", "entries": [{"bp_id": "C-0", "mmr_leaf": leaf0.hex(), "mmr_size": 1, "mmr_root_after": root0}]}))
    for k, v in dict(ROOT=tmp_path, E2E_DIR=tmp_path / "e2e", LEDGER=tmp_path / "e2e/ledger.json", COMP_LEDGER=comp).items():
        monkeypatch.setattr(L, k, v)
    (tmp_path / "a.txt").write_text("one"); (tmp_path / "b.txt").write_text("two")
    return tmp_path

def test_chain_parents_and_verify_pass(lineage):
    e1 = L.create_breakpoint("bp1.json", [("a.txt", "K", "g")])
    e2 = L.create_breakpoint("bp2.json", [("b.txt", "K", "g")])
    assert e2["parent_root"] == e1["mmr_root_after"]
    assert e1["parent_root"] == L.comp_ledger_tip()["mmr_root"]
    assert [r["verify_state"] for r in L.verify_lineage()] == ["PASS", "PASS"]

def test_tampered_atom_detected(lineage):
    L.create_breakpoint("bp1.json", [("a.txt", "K", "g")])
    (lineage / "a.txt").write_text("changed")
    r = L.verify_lineage()[0]
    assert r["verify_state"] == "FAIL" and any("ATOM_MISMATCH" in x for x in r["errors"])

def test_parent_mismatch_detected(lineage):
    L.create_breakpoint("bp1.json", [("a.txt", "K", "g")])
    d = json.loads(L.LEDGER.read_text()); 
    doc = json.loads((lineage / "e2e/bp1.json").read_bytes()); doc["parent_root"] = "00" * 32
    (lineage / "e2e/bp1.json").write_bytes(L.canonical(doc))
    assert L.verify_lineage()[0]["verify_state"] == "FAIL"

def test_ledger_root_forgery_detected(lineage):
    L.create_breakpoint("bp1.json", [("a.txt", "K", "g")])
    d = json.loads(L.LEDGER.read_text()); d["entries"][0]["mmr_root_after"] = "11" * 32
    L.LEDGER.write_bytes(L.canonical(d))
    r = L.verify_lineage()[0]
    assert r["verify_state"] == "FAIL" and "MMR_ROOT_MISMATCH" in r["errors"]

def test_mitosis_blocked_without_key():
    m = L.Mitosis("office", {})
    assert m.auth()["state"] == "BLOCKED"


def test_breakpoint_and_ledger_writes_are_secret_scanned(lineage):
    name = "t" + "k_abcdefghij12.txt"          # token-shaped filename lands in the breakpoint JSON
    (lineage / name).write_text("x")
    with pytest.raises(ValueError, match="SECRET_SCAN=FAIL"):
        L.create_breakpoint("bp_secret.json", [(name, "K", "g")])
    assert not (lineage / "e2e/bp_secret.json").exists() and not L.LEDGER.exists()

def test_mitosis_sdk_is_pinned():
    assert L.MI_SDK_SPEC.startswith("@mitosislabs/sdk@") and not L.MI_SDK_SPEC.endswith("@latest")
    import re; assert re.search(r"@\d+\.\d+\.\d+$", L.MI_SDK_SPEC)


def test_mitosis_cli_is_lockfile_pinned():
    import json as _j
    pkg = _j.loads((L.MI_CLI_DIR / "package.json").read_text())
    lock = _j.loads((L.MI_CLI_DIR / "package-lock.json").read_text())
    assert pkg["dependencies"]["@mitosislabs/sdk"] == "0.27.2"            # exact, no range
    entry = lock["packages"]["node_modules/@mitosislabs/sdk"]
    assert entry["version"] == "0.27.2" and entry["integrity"].startswith("sha512-")
