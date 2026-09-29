# Zenodo upload plan

## Precondition

Do not publish while `ZENODO_RIGHTS_MATRIX.json` is unresolved.

## Finalization sequence

1. Approve separate licenses for the preprint, FCG dataset, and software scripts.
2. Set the actual publication date in both metadata files.
3. Decide whether to reserve both DOIs before rebuilding final PDFs.
4. If reserving: create two Zenodo drafts with `prereserve_doi=true`; capture both draft/DOI receipts.
5. Cross-link the records: preprint `isSupplementedBy` dataset DOI; dataset `isSupplementTo` preprint DOI.
6. If DOI text is inserted into PDFs, rebuild PDFs and recompute every affected SHA-256 and publication breakpoint.
7. Run canonical FCG validation.
8. Run derived Parquet/DuckDB build on a runtime with `pyarrow` and `duckdb`.
9. Run secret scan and rights audit.
10. Freeze `ZENODO_FILE_MANIFEST.json` and final `SHA256SUMS.txt`.
11. Create the next publication breakpoint only after bytes are frozen.
12. Upload files to the two drafts.
13. Validate server-side draft metadata/files.
14. Publish only after operator review using the explicit `--publish` action.

No existing v0.1.0 predecessor bytes or roots may be retroactively changed.
