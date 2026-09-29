#!/usr/bin/env python3
"""Build Parquet projections and DuckDB query database from canonical Vithia JSONL.

Canonical JSONL remains authoritative for identity/custody. Parquet/DuckDB are
derived query artifacts. This script intentionally fails rather than silently
substituting formats when pyarrow or duckdb are unavailable.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
CANON = ROOT / "fcg" / "canonical"
PARQUET = ROOT / "fcg" / "parquet"
DBDIR = ROOT / "fcg" / "database"
SCHEMAS = ROOT / "fcg" / "schemas"

MAP = {
    "sources": "sources.jsonl",
    "content_fcos": "content_fcos.jsonl",
    "occurrence_fcos": "occurrence_fcos.jsonl",
    "contexts": "context_fcos.jsonl",
    "transitions": "transition_fcos.jsonl",
    "fcg_edges": "fcg_edges.jsonl",
    "claims": "claims.jsonl",
    "claim_evidence": "evidence_bindings.jsonl",
    "experiments": "experiments.jsonl",
    "results": "results.jsonl",
    "datasets": "datasets.jsonl",
    "citations": "citations.jsonl",
    "breakpoints": "breakpoints.jsonl",
    "mmr_events": "mmr_events.jsonl",
    "artifact_registry": "artifact_registry.jsonl",
}

def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def read_jsonl(path: Path):
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows

def main() -> int:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
        import duckdb
    except Exception as exc:
        print(f"DERIVED_BUILD=BLOCKED_MISSING_DEPENDENCY: {exc}", file=sys.stderr)
        print("Required: pyarrow, duckdb", file=sys.stderr)
        return 2

    PARQUET.mkdir(parents=True, exist_ok=True)
    DBDIR.mkdir(parents=True, exist_ok=True)

    lineage = {}
    for table, filename in MAP.items():
        src = CANON / filename
        rows = read_jsonl(src)
        out = PARQUET / f"{table}.parquet"
        table_obj = pa.Table.from_pylist(rows)
        pq.write_table(table_obj, out, compression="zstd")
        lineage[table] = {
            "derived_from": str(src.relative_to(ROOT)),
            "source_sha256": sha256_file(src),
            "parquet": str(out.relative_to(ROOT)),
            "parquet_sha256": sha256_file(out),
            "row_count": len(rows),
            "schema_version": "VITHIA_PUBLICATION_FCG_SCHEMA_V1",
        }

    db = DBDIR / "vithia_publication_fcg_v0.1.0.duckdb"
    if db.exists():
        db.unlink()
    con = duckdb.connect(str(db))
    try:
        for table in MAP:
            pp = (PARQUET / f"{table}.parquet").as_posix()
            con.execute(f'CREATE VIEW v_{table} AS SELECT * FROM read_parquet(?)', [pp])

        # Stable public aliases requested by the publication FCG contract.
        con.execute("CREATE VIEW v_content AS SELECT * FROM v_content_fcos")
        con.execute("CREATE VIEW v_occurrences AS SELECT * FROM v_occurrence_fcos")
        con.execute("CREATE VIEW v_artifacts AS SELECT * FROM v_artifact_registry")
        con.execute("CREATE VIEW v_edges AS SELECT * FROM v_fcg_edges")

        con.execute("""CREATE VIEW v_content_reuse AS
            SELECT content_fco_ref, COUNT(*) occurrence_count
            FROM v_occurrences GROUP BY content_fco_ref""")
        con.execute("""CREATE VIEW v_occurrence_multiplicity AS
            SELECT * FROM v_content_reuse WHERE occurrence_count > 1""")
        con.execute("""CREATE VIEW v_not_tested AS
            SELECT * FROM v_claims
            WHERE claim_state IN ('NOT_TESTED','NOT_COMPUTED','NOT_COMPARABLE','UNKNOWN')""")
        con.execute("""CREATE VIEW v_negative_results AS
            SELECT * FROM v_claims
            WHERE claim_state IN ('NOT_SUPPORTED','FAIL_TO_REJECT_H0','NEGATIVE')""")
        con.execute("""CREATE VIEW v_claim_ceiling AS
            SELECT claim_id, claim_state, forbidden_stronger_wording AS claim_ceiling
            FROM v_claims""")
        con.execute("""CREATE VIEW v_claim_to_source_path AS
            SELECT e.claim_ref, e.manuscript_occurrence_ref, e.evidence_refs
            FROM v_claim_evidence e""")
        con.execute("""CREATE VIEW v_claim_to_experiment_path AS
            SELECT c.claim_id, c.experiment_id, e.object_id AS experiment_object_id
            FROM v_claims c LEFT JOIN v_experiments e
            ON c.experiment_id = e.experiment_id""")
        con.execute("""CREATE VIEW v_experiment_to_result_path AS
            SELECT e.experiment_id, r.object_id AS result_object_id, r.claim_ref
            FROM v_experiments e LEFT JOIN v_results r
            ON r.experiment_ref = e.object_id""")
        con.execute("""CREATE VIEW v_breakpoint_to_artifacts AS
            SELECT breakpoint_id, artifact_path, artifact_sha256, breakpoint_root
            FROM v_breakpoints""")
        con.execute("""CREATE VIEW v_unknown_provenance AS
            SELECT object_id, provenance_state FROM v_claims
            WHERE provenance_state = 'UNKNOWN'""")
    finally:
        con.close()

    receipt = {
        "schema": "VITHIA_DERIVED_FCG_BUILD_RECEIPT_V1",
        "canonical_authority": "fcg/canonical/*.jsonl",
        "parquet_state": "PASS",
        "duckdb_state": "PASS",
        "duckdb_sha256": sha256_file(db),
        "tables": lineage,
    }
    out_receipt = ROOT / "fcg" / "verification" / "DERIVED_FCG_BUILD_RECEIPT.json"
    out_receipt.parent.mkdir(parents=True, exist_ok=True)
    out_receipt.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("PARQUET_GENERATION=PASS")
    print("DUCKDB_OPEN_QUERY=PASS")
    print(f"DUCKDB_SHA256={receipt['duckdb_sha256']}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
