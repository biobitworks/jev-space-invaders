# Vithia 0-Vita-1 Publication FCG Data Dictionary

## Status

Schema: `VITHIA_PUBLICATION_FCG_SCHEMA_V1`  
Release scope: `v0.1.0`  
Canonical identity layer: JSONL under `fcg/canonical/`.

## Identity model

**ContentFCO** represents exact canonical content bytes. Where a SHA-256 is present it is an identity/deduplication key, not a semantic score.

**OccurrenceFCO** represents one contextual occurrence of content. Multiple occurrences may reference the same ContentFCO without being collapsed.

**ContextFCO** represents governed state used to interpret/materialize evidence.

**TransitionFCO** represents an explicit predecessor-to-successor state transition. Historical predecessor objects remain immutable.

## Core tables

| File | Unit |
|---|---|
| `sources.jsonl` | external/public source registry entries |
| `content_fcos.jsonl` | exact content objects |
| `occurrence_fcos.jsonl` | content occurrences |
| `context_fcos.jsonl` | governed contexts |
| `transition_fcos.jsonl` | explicit state transitions |
| `fcg_edges.jsonl` | typed declared relationships |
| `claims.jsonl` | governed publication claims |
| `evidence_bindings.jsonl` | manuscript claim/evidence bindings |
| `experiments.jsonl` | experiment registry |
| `results.jsonl` | claim-level result projections |
| `datasets.jsonl` | dataset registry |
| `citations.jsonl` | citation/source projection |
| `breakpoints.jsonl` | scientific breakpoint projection |
| `mmr_events.jsonl` | recovered scientific/publication MMR events |
| `artifact_registry.jsonl` | release artifacts and hashes |
| `PUBLICATION_CLAIM_PATHS.jsonl` | claim-to-evidence/query routes |

## Interpretation boundaries

A `SUPPORTED_BY` edge means the governed registry binds evidence to a claim. It does **not** itself prove the claim.

A Merkle or MMR root commits exact declared inputs/order under its construction algorithm. It does **not** establish scientific truth.

The v0.1.0 release preserves `NOT_SUPPORTED`, `FAIL_TO_REJECT_H0`, `NOT_COMPUTED`, `DEFERRED_NOT_FAILED`, and `INPUT_FROZEN_NO_DECIDER_CALLS` states rather than upgrading them.

## Derived formats

Parquet and DuckDB are analytical/query projections only. They must record the canonical JSONL hashes and generator version from which they were produced. A derived file hash identifies that generated file, not the underlying scientific truth.
