# MSM-AIS v0.2 Preregistration — Anticube + G*/DeltaG* + Adaptive Vithia

**Project:** AGENTICLS_PUBLICATION / Vithia 0-Vita-1  
**Status:** PREREGISTERED_DESIGN_SUCCESSOR — NOT EXECUTED  
**Baseline spec:** `publication/successors/MSM_AIS_ANTICUBE_GSTAR_BASELINE_V02.md`  
**Predecessor release:** `publication/v0.1.0@2ce9cd8a9b2c3bba63515a7e7eb6cb072f3a8a4c`

## 1. Purpose

Freeze the next experimental version before additional inference capability is consumed.

The experiment family tests whether the v0.2 formal corrections and MSM-AIS integration are mechanically valid and whether Anticube + comparable G*/DeltaG* state can improve Vithia context selection without rewriting source evidence or conflating custody with truth.

No result is implied by this preregistration.

## 2. Global invariants

Every experiment MUST preserve:

```
SOURCE_BYTES_IMMUTABLE=YES
CORRECTIONS_CREATE_SUCCESSORS=YES
HASH_DISTANCE_USED_AS_SEMANTIC_DISTANCE=NO
MERKLE_INCLUSION_TREATED_AS_TRUTH=NO
FCG_EDGE_TREATED_AS_CAUSALITY=NO
DELTA_GSTAR_AT_GENESIS=NOT_COMPUTED_NO_COMPARABLE_PREDECESSOR
ORIGIN_RELATIVE_ZERO=DEFINITIONAL_ONLY
PAIRWISE_TOLERANCE_TREATED_AS_EQUIVALENCE_RELATION=NO
ANTICUBE_CANONICAL_CLASSES=
  SELF_SAFE
  SELF_UNSAFE
  NONSELF_SAFE
  NONSELF_UNSAFE
  UNKNOWN
```

Any experiment that violates a global invariant is INVALID_EXECUTION.

## 3. Versioning

```
EXPERIMENT_FAMILY=
MSM_AIS_V02

FORMAL_BASELINE=
MSM_AIS_ANTICUBE_GSTAR_BASELINE_V02

EXECUTION_STATE=
NOT_EXECUTED

MODEL_CAPABILITY=
RECOVER_AT_EXECUTION_TIME

MODEL/ENVIRONMENT CHANGES=
REQUIRE NEW SUCCESSOR PREREGISTRATION
unless explicitly listed as a frozen factor.
```

## 4. Tier A — formal / non-inference experiments

These can run without frontier-model inference and should be completed before Tier B.

---

## EXP-A1 — Equivalence-contract correctness

### Question

Does the successor contract correctly distinguish exact identity, occurrence identity, true partition classes, pairwise tolerance compatibility, and fixed-reference acceptance?

### Frozen cases

1. exact canonical bytes equal;
2. exact canonical bytes differ;
3. same content under distinct occurrences;
4. deterministic partition/bin membership;
5. pairwise tolerance transitivity counterexample;
6. fixed-reference acceptance;
7. rule-version successor;
8. retrospective comparison under a newer standard;
9. UNKNOWN boundary;
10. NOT_COMPARABLE boundary.

### Required counterexample

[
x=0,quad y=0.75,quad z=1.5,quad epsilon=1.
]

Required:

[
x\sim y,quad y\sim z,quad x\not\sim z.
]

### Null

[
H_0:
	ext{the implementation permits pairwise tolerance to create transitive equivalence-class membership.}
]

### Pass gate

```
ALL_EXACT_IDENTITY_TESTS=PASS
ALL_OCCURRENCE_SEPARATION_TESTS=PASS
PAIRWISE_TOLERANCE_CLASS_CREATION=REJECTED
PARTITION_CLASS_MODE=PASS
FIXED_REFERENCE_MODE=PASS
RULE_VERSION_IMMUTABILITY=PASS
UNKNOWN_NOT_COMPARABLE=PASS
```

No p-value is required; this is a deterministic contract test.

---

## EXP-A2 — Uncertainty calibration

### Question

Are versioned comparison policies mathematically correct under independent, correlated, non-Gaussian, and multivariate uncertainty?

### Cases

1. independent Gaussian:
[
sigma_c^2=sigma_G^2+sigma_X^2.
]

2. correlated:
[
sigma_c^2=
sigma_G^2+sigma_X^2-2\operatorname{Cov}(G,X).
]

3. multivariate Gaussian:
[
d_M^2=(x-mu)^TSigma^{-1}(x-mu).
]

4. empirical quantile;
5. robust MAD;
6. bootstrap interval;
7. domain-specific comparator.

### Null

[
H_0:
	ext{comparison classification differs from the frozen reference implementation.}
]

### Pass gate

All deterministic/simulation cases must match the reference calculation to numerical tolerance frozen in the test manifest.

A chi-square threshold may be used only for the multivariate-normal case.

---

## EXP-A3 — Golden-standard anti-drift

### Question

Can the observed running distribution change without silently mutating the frozen governing standard?

### Design

Freeze:

```
GoldenStandardFCO_v1
```

Feed a gradual synthetic drift series while separately updating:

```
ObservedDistributionFCO_t
```

### Required behavior

```
GoldenStandardFCO_v1 hash = CONSTANT
ObservedDistributionFCO_t = SUCCESSORS
automatic v1 mutation = FORBIDDEN
candidate v2 = NEW FCO
v2 admission = explicit governed action
```

### Pass gate

100% of drift steps preserve the v1 exact identity.

---

## EXP-A4 — Replay interpretation successor

### Question

Can authoritative execution and later replay interpretation disagree without either being overwritten?

### Cases

A. exact replay;
B. exact bytes differ but frozen transform establishes semantic agreement;
C. within expected variance;
D. semantic contradiction;
E. NOT_COMPARABLE decoder/runtime.

### Required objects

```
ActionExecutionFCO_t
ReplayDecoderFCO_v
ReplayActionFCO_t
ReplayComparisonFCO_t
```

### Pass gate

For every case:

```
execution hash unchanged
replay object separately addressable
comparison object separately addressable
semantic state explicit
DeltaG* remains NOT_COMPUTED unless comparable under frozen theta
```

---

## EXP-A5 — Proof versus reconstruction

### Question

Does the system distinguish proof/integrity from sufficient reconstruction state?

### Frozen cases

1. valid proof + reconstruction pass;
2. valid proof + missing dependency;
3. valid proof + reconstruction executes but differs;
4. invalid proof.

### Exact required states

```
PROOF_PASS_RECONSTRUCTION_PASS
PROOF_PASS_RECONSTRUCTION_BLOCKED
PROOF_PASS_RECONSTRUCTION_MISMATCH
PROOF_FAIL
```

### Pass gate

All four cases classify exactly as preregistered.

---

## EXP-A6 — Fragmentum content/occurrence deduplication

### Question

Can exact payloads be stored once while preserving occurrence multiplicity and parent-specific roots?

### Metrics

```
LOGICAL_BYTES
PHYSICAL_NEW_BYTES_WRITTEN
DEDUP_RATIO
POINTER_HIT_RATE
UNCHANGED_ATOM_RATE
CONTENT_FCO_COUNT
OCCURRENCE_FCO_COUNT
PARENT_ROOT_COUNT
```

### Structural gates

```
same bytes -> same ContentFCO
different occurrence -> distinct OccurrenceFCO
same ContentFCO may appear under multiple parent roots
occurrence multiplicity is never deduplicated away
```

### Empirical storage hypothesis

[
H_0:
\operatorname{PHYSICAL\_NEW\_BYTES}
\ge
\operatorname{LOGICAL\_BYTES}.
]

Expected direction only:

[
\operatorname{PHYSICAL\_NEW\_BYTES}
<
\operatorname{LOGICAL\_BYTES}
]

when duplicated payloads are present.

No minimum effect size is asserted until the frozen corpus for this experiment is selected.

## 5. Tier B — inference/context experiments

Tier B requires additional model inference capability. It MUST NOT execute until Tier A passes and the exact models/runtimes/seeds are frozen in an execution successor.

---

## EXP-B1 — Changed-frontier Vithia

### Question

Can context materialization operate over changed/relevant atoms rather than rematerializing the full FCG while preserving downstream decision behavior?

### Arms

```
B1-A RAW_FULL
B1-B FIXED_L1
B1-C CONTENT_HASH_FRONTIER
B1-D CONTEXTUAL_FRONTIER
```

`CONTEXTUAL_FRONTIER` may reintroduce unchanged content when occurrence, Anticube, comparable G*/DeltaG*, uncertainty, or relevant typed-edge state changes.

### Frozen factors at execution

```
same environment
same seeds
same action ontology
same downstream model
same model version
same inference parameters
same model temperature
same evaluation window
```

### Primary metrics

```
MODEL_CONTEXT_BYTES
MODEL_CONTEXT_TOKENS
PHYSICAL_NEW_BYTES_WRITTEN
POINTER_HIT_RATE
VITHIA_PREPROCESS_MS
MODEL_INFERENCE_MS_P50
MODEL_INFERENCE_MS_P95
END_TO_END_MS_P50
END_TO_END_MS_P95
DECISION_AGREEMENT_WITH_RAW
FALLBACK_RATE
```

### Performance gate for a positive efficiency result

A context-selection arm is efficiency-positive only if:

```
median MODEL_CONTEXT_BYTES reduction vs RAW >= 20%
AND
median MODEL_INFERENCE_MS reduction vs RAW >= 10%
AND
DECISION_AGREEMENT_WITH_RAW >= 0.90
AND
fallback rate does not increase by > 0.05 absolute
```

If any gate fails:

```
EFFICIENCY_CLAIM=NOT_SUPPORTED
```

Score/reward remains secondary unless separately preregistered.

---

## EXP-B2 — Anticube + G*/DeltaG* adaptive context

### Question

Does adding governed contextual state improve context allocation relative to content-change-only selection?

### Arms

```
B2-A CONTENT_HASH_FRONTIER
B2-B CONTENT_PLUS_OCCURRENCE
B2-C CONTENT_OCCURRENCE_PLUS_ANTICUBE
B2-D CONTENT_OCCURRENCE_ANTICUBE_PLUS_GSTAR
```

### Primary comparison

B2-D vs B2-A.

### Primary endpoints

```
MODEL_CONTEXT_BYTES
MODEL_INFERENCE_MS_P50
DECISION_AGREEMENT_WITH_RAW
UNNECESSARY_EXPANSION_RATE
MISSED_CHALLENGE_RATE
UNKNOWN_RATE
```

### Null

[
H_0:
	ext{Anticube + comparable G*/DeltaG* provides no improvement in the context-efficiency frontier over content-change-only selection.}
]

### Positive result gate

```
context bytes reduction >= 20% vs RAW
AND
decision agreement with RAW >= 0.90
AND
missed challenge rate <= 0.05
AND
unnecessary expansion rate lower than B2-A
```

Latency is reported separately and MUST include Vithia preprocessing.

---

## EXP-B3 — Emergent path / Golden Path

### Question

Can the currently selected path change when contradictory evidence is admitted without modifying any predecessor source atom?

### Design

Construct at least three initially admissible candidate paths with a frozen versioned path-weighting policy.

Admit evidence in a predetermined order that:

1. supports path A;
2. creates a tie/uncertainty state;
3. challenges path A;
4. supports path B.

### Required invariants

```
source atom hashes unchanged
path distribution changes only by successor state
tie rule explicit
abstain/UNKNOWN explicit
selected path may change
selected path != truth claim
```

### Pass gate

All predetermined transitions are represented without historical mutation.

---

## EXP-B4 — Feynman–Kac candidate scaffold

### Status

```
CANDIDATE_FORMALISM
NOT_CANONICAL_DELTAGSTAR
```

### Question

Can a dimensionally coherent path-weighting scaffold be implemented without conflating it with Anticube or G*/DeltaG*?

### Candidate discrete form

For a dimensionless transition index:

[
w(\Gamma)
\propto
\exp\left(
-\sum_{k=t}^{T-1} V_\psi(\mathcal F_k)
\right),
]

where (V_\psi) is explicitly dimensionless per transition.

### Tests

```
exponent dimensionless
weights finite
weights nonnegative
normalization finite
declared monotonicity cases pass
Anticube remains separate companion state
DeltaG* remains separately defined
```

No inference-performance or scientific-truth claim follows from passing this experiment.

## 6. Multiple-comparison policy

Tier A deterministic contract tests use exact pass/fail gates, not significance tests.

Tier B statistical analyses MUST freeze:

```
sample size
paired unit
primary endpoint
confidence interval method
multiple-comparison correction
noninferiority/equivalence margins
```

in the execution successor before any Tier B model calls.

Exploratory metrics may be reported but cannot replace the preregistered primary decision.

## 7. Failure preservation

Every failed/null/partial result remains addressable.

Allowed states include:

```
SUPPORTED
NOT_SUPPORTED
FAIL_TO_REJECT_H0
PARTIAL
NEGATIVE
ABSTAIN
NOT_TESTED
NOT_COMPUTED
NOT_COMPARABLE
UNKNOWN
INVALID_EXECUTION
```

## 8. Claim ceiling before execution

The existence of this preregistration establishes only:

```
FORMAL_DESIGN_FROZEN=YES
EXPERIMENTS_EXECUTED=NO
ANTICUBE_ADAPTIVE_CONTEXT_EFFECT=NOT_TESTED
DELTAGSTAR_ADAPTIVE_CONTEXT_EFFECT=NOT_TESTED
GOLDEN_PATH_EXPERIMENT=NOT_TESTED
FEYNMAN_KAC_SCAFFOLD=NOT_TESTED
```

It MUST NOT be cited as experimental validation.
