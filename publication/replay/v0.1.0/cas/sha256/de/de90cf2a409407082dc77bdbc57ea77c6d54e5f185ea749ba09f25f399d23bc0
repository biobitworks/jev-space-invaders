# Zenodo-ready Vithia 0-Vita-1 publication/FCG package

This directory is a **draft release successor** built from the frozen `publication/v0.1.0` evidence package. It does not mutate historical publication or scientific breakpoints.

## Record split

Two separately citable Zenodo records are planned:

1. **Preprint** — manuscript, supplement, source/reproducibility material, and bounded claim/evidence manifests.
2. **Publication FCG dataset** — canonical JSONL FCO/FCG records, analytical projections, query database, schemas, and verification receipts.

## Canonical versus derived

`fcg/canonical/*.jsonl` is the canonical machine-readable identity/custody layer for this package.

Parquet and DuckDB are **derived query artifacts**. They must be generated from the canonical JSONL using `fcg/scripts/build_derived_fcg.py` and must not be treated as a replacement for canonical source identity.

## Current release gate

The recovered v0.1.0 release gate remains blocked by:

- disclosed historical publication atom replay gap at VITA-PUB-BP-0015;
- release license not yet established;
- Zenodo authentication not available to this chat.

The historical publication MMR chain is recorded as PASS while publication atom replay is PARTIAL. The unavailable atom is an ephemeral `.pyc` artifact; this package does not rewrite that history.

## Security

Never commit `ZENODO_TOKEN`. API scripts read it only from the environment and default to dry-run. Publishing requires an explicit `--publish` flag.

## Claim ceiling

Hashes establish identity/deduplication. Typed FCG edges declare relationships. Merkle/MMR membership establishes declared integrity/order/custody under the relevant construction. None of these mechanisms independently establishes scientific truth or causality.
