"""E0 addressability. See docs/prereg/E0_ADDRESSABILITY.md."""
from __future__ import annotations

import random

from experiments.common import ds_dir, prereg_ref, read_jsonl, write_jsonl, write_manifest
from src.kernels.address import address_str, parse_address, rank, state_content_id, unrank

EXP, IN_ID, OUT_ID = "E0_ADDRESSABILITY", "S01_ADDRESSABILITY_EVAL_V1", "S01_ADDRESSABILITY_RESULTS_V1"
SPACES = [(2, 8), (2, 64), (3, 32), (26, 20), (256, 16)]
PER_SPACE = 2000
CODE = ["experiments/e0_babel.py", "src/kernels/address.py", "src/s01/canon.py"]


def build_input() -> dict:
    rows = []
    for si, (k, n) in enumerate(SPACES):
        rng = random.Random(1000 + si)
        states = [[0] * n, [k - 1] * n] + [[rng.randrange(k) for _ in range(n)] for _ in range(PER_SPACE)]
        rows += [{"space": f"k{k}n{n}", "k": k, "n": n, "i": i, "state": s} for i, s in enumerate(states)]
    d = ds_dir(IN_ID)
    write_jsonl(d / "rows.jsonl", rows)
    return write_manifest(d, dataset_id=IN_ID, schema="rows: {space,k,n,i,state}", kind="evaluation",
                          source="generated", generation_code=CODE,
                          config={"spaces": SPACES, "per_space": PER_SPACE}, seeds=[1000 + i for i in range(len(SPACES))],
                          claim_ceiling="synthetic finite states; no external data")


def run() -> dict:
    inp = ds_dir(IN_ID) / "rows.jsonl"
    out, addr_seen, cid_seen = [], {}, {}
    rt_fail = eq_fail = 0
    for r in read_jsonl(inp):
        k, n, s = r["k"], r["n"], r["state"]
        a = rank(s, k)
        astr = address_str(a, k, n)
        a2, k2, n2 = parse_address(astr)
        back = unrank(a2, k2, n2)
        cid = state_content_id(s, k)
        ok = back == s and a2 == a
        rt_fail += not ok
        clash = astr == cid or astr.split(":")[1] == cid.split(":")[1] or a == int(cid.split(":")[1], 16)
        eq_fail += clash
        key = (r["space"], tuple(s))
        addr_seen.setdefault((r["space"], a), set()).add(key)
        cid_seen.setdefault(cid, set()).add(key)
        out.append({"space": r["space"], "i": r["i"], "address": astr, "content_id": cid, "roundtrip": ok})
    d = ds_dir(OUT_ID)
    sha, _, nrows = write_jsonl(d / "rows.jsonl", out)
    addr_coll = sum(len(v) - 1 for v in addr_seen.values())
    cid_coll = sum(len(v) - 1 for v in cid_seen.values())
    # duplicates in the input (same state twice) are not collisions; count distinct only
    m = write_manifest(d, dataset_id=OUT_ID, schema="rows: {space,i,address,content_id,roundtrip}", kind="output",
                       source=IN_ID, generation_code=CODE, config={}, seeds=[],
                       parent_evidence=[IN_ID], claim_ceiling="deterministic computation over the frozen input")
    claims = [
        {"id": "H0a", "state": "SUPPORTED" if rt_fail == 0 else "NOT_SUPPORTED", "roundtrip_failures": rt_fail, "rows": nrows},
        {"id": "H0b", "state": "SUPPORTED" if addr_coll == 0 else "NOT_SUPPORTED", "address_collisions": addr_coll},
        {"id": "H0c", "state": "SUPPORTED" if cid_coll == 0 else "NOT_SUPPORTED", "content_id_collisions": cid_coll},
        {"id": "H0d", "state": "SUPPORTED" if eq_fail == 0 else "NOT_SUPPORTED", "address_equals_hash_rows": eq_fail},
        {"id": "H0e", "state": "SEE_REPLAY_CHECK", "output_rows_sha256": sha},
    ]
    terminal = "SUPPORTED" if all(c["state"] in ("SUPPORTED", "SEE_REPLAY_CHECK") for c in claims) else "NOT_SUPPORTED"
    return {"experiment_id": EXP, "question": "Can finite canonical states be reversibly addressed independently from their cryptographic content identity?",
            "preregistration": prereg_ref("E0_ADDRESSABILITY.md"), "output_manifest": m,
            "terminal_state": terminal, "claims": claims, "not_tested": []}
