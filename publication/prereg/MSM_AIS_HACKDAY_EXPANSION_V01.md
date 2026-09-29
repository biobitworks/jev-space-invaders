# Vithia / MSM-AIS Hack Day Experiment Expansion v0.1

**Project:** AGENTICLS_PUBLICATION / VITHIA_SPACE  
**Event:** AI Conference Hack Day 2026 — September 29, 2026  
**Status:** PREREGISTERED_DESIGN_SUCCESSOR — NOT EXECUTED  
**Publication parent:** `publication/msm-ais-anticube-deltagstar-baseline-v02-20260929@09c4cae4f5f30fd4dd1fd486fd47fda3a4f8c07a`  
**Upstream DuploCloud source:** `duplocloud/devkit@e9f016fd90a67611907fcf673701351669eaa47d`

## 1. Purpose

Use the Hack Day as a bounded external execution environment for the next MSM-AIS/Vithia experiments.

The event is an implementation opportunity, not a license to upgrade prior claims.

Tomorrow's work should test whether Vithia can operate as a governed context layer inside a third-party agent platform while preserving:

- exact content identity;
- occurrence/context identity;
- typed FCG relationships;
- bounded context projection;
- successor state;
- explicit challenge/unknown states;
- custody distinct from truth;
- reconstruction distinct from proof.

No result is implied by this preregistration.

## 2. External platform mapping

The initial integration hypothesis is:

```text
DuploCloud Provider / Credential / Scope
        ↓
authorized external capability boundary

DuploCloud Skill / Persona
        ↓
declared agent capability / standing behavior

DuploCloud Workspace / Ticket
        ↓
bounded task context

Vithia
        ↓
FCO atomization → FCG state → bounded ContextProjectionFCO

downstream model / agent
        ↓
tool action

observed result
        ↓
successor FCO / FCG state
```

This mapping is a proposed integration model until executed.

## 3. EXP-H1 — External-platform state recovery

### Question

Can a new DuploCloud ticket/session continue from persisted Vithia state without reconstructing the predecessor from chat memory?

### Null

`H0_H1`: a fresh session cannot recover the exact declared predecessor context/custody state.

### Frozen primary checks

```text
PREDECESSOR_FCO_ROOT_EQUALITY
CONTEXT_PROJECTION_HASH_EQUALITY
AUTHORIZED_SCOPE_IDENTITY
SUCCESSOR_PARENT_BINDING
```

### Positive gate

All exact-identity checks must pass.

Narrative similarity is insufficient.

## 4. EXP-H2 — Bounded-context materialization

### Question

Can Vithia materialize a smaller model-visible context while retaining exact references to omitted evidence?

### Arms

```text
H2-A RAW / full available task evidence
H2-B VITHIA_BOUNDED
```

### Primary metrics

```text
LOGICAL_EVIDENCE_BYTES
MODEL_CONTEXT_BYTES
MODEL_CONTEXT_TOKENS
VITHIA_PREPROCESS_MS
MODEL_INFERENCE_MS
OMITTED_EVIDENCE_POINTER_COUNT
CONTEXT_PROJECTION_HASH
```

### Claim gate

A compression/efficiency claim requires measured reduction in model-visible context.

A correctness-preservation claim requires a separately frozen decision-quality criterion; it must not be inferred from smaller context alone.

## 5. EXP-H3 — Same-content / changed-context reactivation

### Question

Can Vithia re-materialize an unchanged ContentFCO when its occurrence, relationship, Anticube state, uncertainty, or comparable contextual state changes?

### Invariant

```text
same content hash
does not imply
same contextual relevance
```

### Required fixture

At least one atom whose exact bytes remain unchanged while a new relationship or challenge state is introduced.

### Positive gate

The contextual successor becomes model-visible while the underlying ContentFCO hash remains unchanged.

## 6. EXP-H4 — Neo4j-backed FCG adapter

### Status

`OPTIONAL_SPONSOR_LANE` until credentials/access are available.

### Question

Can the typed FCG be written to and queried from Neo4j through the documented DuploCloud MCP path without weakening FCO identity?

### Required operations

```text
write at least one FCO node
write at least one typed edge
query the supporting path for a current ContextProjectionFCO
return exact FCO IDs in the result
```

### Claim gate

`NEO4J_FCG_INTEGRATION=PASS` only if a live write and read/query-back both succeed.

A configured but idle integration does not count as PASS.

## 7. EXP-H5 — Downstream reader/provider separation

### Status

`OPTIONAL_SPONSOR_LANE`.

### Question

Can the same frozen ContextProjectionFCO be sent to a downstream model served by a provider-pinned Crusoe or Nebius route while preserving the Vithia context compiler as a separate layer?

### Required invariant

```text
same frozen context bytes
same question
provider identity observed
fallback disabled for provider-pinning test
```

### Claim gate

Provider execution proves only that the frozen context was consumed by the observed provider/model.

It does not establish model equivalence or superiority.

## 8. EXP-H6 — Proof versus reconstruction continuation

Tomorrow's external execution must preserve the distinction:

```text
PROOF_PASS
!=
RECONSTRUCTION_PASS
```

If a persisted Vithia state has valid custody but a fresh DuploCloud session cannot reconstruct the required task state, classify:

```text
PROOF_PASS_RECONSTRUCTION_BLOCKED
```

or:

```text
PROOF_PASS_RECONSTRUCTION_MISMATCH
```

as appropriate.

Do not relabel the predecessor evidence as corrupt.

## 9. EXP-H7 — Anticube / G*/DeltaG* context-expansion observation

### Status

`PROPOSED / EXPLORATORY` unless the current v0.2 formal preregistration gates are satisfied.

Do not invent a new G*/DeltaG* formula during the Hack Day.

Allowed observation:

- exact content unchanged;
- Anticube companion state changed;
- typed FCG relationship changed;
- uncertainty changed;
- context expanded or remained bounded.

`DELTA_GSTAR=NOT_COMPUTED` remains valid whenever comparability under the frozen functional is not established.

## 10. Failure preservation

Preserve all failures and blocked sponsor states.

Allowed states:

```text
PASS
FAIL
PARTIAL
BLOCKED
NOT_TESTED
NOT_COMPUTED
NOT_COMPARABLE
UNKNOWN
INVALID_EXECUTION
```

Do not tune away an unexpected failure before first preserving its receipt.

## 11. Execution order for September 29

```text
H0 recover exact predecessor + verify local DuploCloud installation
H1 external-platform state recovery
H2 bounded-context materialization
H3 same-content / changed-context reactivation

then, if time remains:

H4 Neo4j-backed FCG
H5 provider-pinned downstream reader

H6 proof/reconstruction classification applies throughout
H7 Anticube/G*/DeltaG* remains exploratory unless preregistered conditions are met
```

The six-hour event should prioritize the smallest live end-to-end experiment over adding unexecuted integrations.

## 12. Publication relationship

These experiments are successors to the v0.2 MSM-AIS preregistration.

They MUST NOT be inserted retrospectively into the frozen `publication/v0.1.0` evidence lock.

After execution, the publication lane may admit bounded results as successor evidence with explicit labels.

## 13. Current claim ceiling

```text
HACKDAY_EXPERIMENT_EXPANSION_PREREGISTERED=YES
HACKDAY_EXPERIMENTS_EXECUTED=NO
DUPLOCLOUD_VITHIA_INTEGRATION=NOT_TESTED
NEO4J_FCG_INTEGRATION=NOT_TESTED
CRUSOE_NEBIUS_READER_INTEGRATION=NOT_TESTED
ANTICUBE_ADAPTIVE_EFFECT=NOT_TESTED
DELTAGSTAR_ADAPTIVE_EFFECT=NOT_TESTED
```
