# MSM-AIS + Anticube + G*/DeltaG* Baseline Specification v0.2

**Project:** AGENTICLS_PUBLICATION / Vithia 0-Vita-1  
**Status:** PUBLICATION_SUCCESSOR_BASELINE — NOT YET SEALED AS A RELEASE  
**Predecessor:** `publication/v0.1.0@2ce9cd8a9b2c3bba63515a7e7eb6cb072f3a8a4c`  
**Successor rule:** predecessor bytes are immutable; corrections create successors.

## 1. Purpose

This document freezes the first publication-successor baseline for the combined architecture:

```
MSM-AIS
+
Fragmentum-style exact content / occurrence identity
+
typed FCO / FCG state
+
Anticube companion classification
+
versioned G* / DeltaG* contextual-state comparison
+
Vithia bounded context projection
+
downstream System-1 decision
+
successor observation
+
Merkle / MMR custody
```

The novelty claim is intentionally scoped to the **integration and operational coupling** of these components. This document does not claim that hashing, Merkle DAGs, provenance graphs, replay, statistical equivalence, prompt compression, System 0, or System 1 were individually invented here.

## 2. Distinguish external "System 0" from Vithia-S0

External literature uses **System 0** for an AI-mediated cognitive layer that shapes the informational substrate preceding human System 1 and System 2 cognition.

Vithia uses the string **S0** more narrowly:

```
Vithia-S0
=
deterministic evidence/context compiler
```

It is not a claim of priority over the external term "System 0".

The public Vithia execution boundary is:

[
E_t
\xrightarrow{S_0}
C_t
\xrightarrow{\Pi_t}
P_t
\xrightarrow{S_1}
D_t
\xrightarrow{\mathrm{world}}
O_{t+1}.
]

Where:

- (E_t): governed evidence available at transition (t);
- (S_0): deterministic Vithia context compiler;
- (C_t): finite contextual state;
- (Pi_t): bounded context projection/query plan;
- (P_t): materialized ContextPacket;
- (S_1): downstream decision model/agent;
- (D_t): decision/action receipt;
- (O_{t+1}): subsequently observed world result.

Anticube and G*/DeltaG* are companion state variables used by MSM/Vithia to govern or characterize context. They do **not** turn S0 into a decision model.

## 3. Artificial Infinite Systems (AIS)

"AIS" is structural, not a literal infinity claim.

Let the governed project state at transition (t) be a finite state:

[
\mathcal{F}_t < \infty.
]

A valid successor is:

[
\mathcal{F}_{t+1}
=
T_{\theta_t}(\mathcal{F}_t,E_{t+1}),
]

where the transition policy (	heta_t) is versioned and the predecessor is not mutated.

The AIS property is:

> Every committed state is finite, but a valid successor may itself become a predecessor for another finite successor without requiring historical states to be rewritten.

No claim of infinite memory, infinite compute, or physically infinite execution is made.

## 4. Fragmentum-style identity substrate

For a canonical payload (x):

[
C(x)=H(\operatorname{canon}(x))
]

is exact content identity.

An occurrence is a distinct governed object whose identity may bind declared contextual fields:

[
O_i
=
H\!\left(
C(x),
P_i,
r_i,
p_i,
\tau_i,
v_{\mathrm{occ}}
\right),
]

where the fields are defined by the applicable occurrence schema.

Therefore:

[
C(x)_i=C(x)_j
]

may hold while:

[
O_i\neq O_j.
]

A shared content hash never collapses distinct biological, scientific, temporal, or documentary occurrences.

## 5. Mathematical correction 1 — DeltaG* genesis and origin reference

### 5.1 Contextual state

For immutable content atom (A), define a versioned contextual state:

[
S_{A,t}
=
(C_A,O_{A,t},\mathcal F_t,A_{A,t},U_{A,t},\ldots),
]

where:

- (C_A) is immutable exact content identity;
- (O_{A,t}) is occurrence/context identity;
- (mathcal F_t) is the declared FCG state/subgraph;
- (A_{A,t}) is the Anticube companion state;
- (U_{A,t}) is any declared uncertainty state.

### 5.2 Versioned state functional

A candidate contextual-state functional is only defined on its declared comparable domain:

[
G^*_{\theta}:\mathcal D_{\theta}\rightarrow\mathbb R,
]

with (	heta) binding at minimum:

```
functional version
feature definition
normalization
units / dimensionless declaration
comparison policy
uncertainty policy
boundary semantics
```

In the current Vithia/MSM baseline, (G^*) and (Delta G^*) are **dimensionless contextual/graph-state quantities unless a later successor explicitly declares otherwise**. They are not physical Gibbs free energy.

### 5.3 Predecessor-relative transition

For (t\ge1), only if both states are comparable under the same (	heta):

[
\boxed{
\Delta G^*_{A,t}
=
G^*_{\theta}(S_{A,t})
-
G^*_{\theta}(S_{A,t-1})
}
]

At genesis there is no comparable predecessor:

```
DELTA_GSTAR_FROM_PREDECESSOR=
NOT_COMPUTED_NO_COMPARABLE_PREDECESSOR
```

An artificial numerical zero MUST NOT be stored merely because the state is the first observed state.

### 5.4 Origin-relative displacement

If an origin-relative quantity is useful, define it separately:

[
\boxed{
R^*_{A,t}
=
G^*_{\theta}(S_{A,t})
-
G^*_{\theta}(S_{A,0})
}
]

for comparable states under the same (	heta).

Then:

[
R^*_{A,0}=0
]

**by definition**, not by empirical measurement.

Canonical field distinction:

```
DELTA_GSTAR_FROM_PREDECESSOR
ORIGIN_RELATIVE_GSTAR_DISPLACEMENT
```

These MUST NOT be conflated.

## 6. Anticube baseline

The canonical Anticube classification remains:

```
SELF_SAFE
SELF_UNSAFE
NONSELF_SAFE
NONSELF_UNSAFE
UNKNOWN
```

`UNKNOWN` is the abstain/unresolved state.

`QUESTION` or `CHALLENGE` may be an epistemic/action/disposition field; it is not silently introduced as a fifth or sixth 2x2 class.

At source ingestion:

```
SELFNESS=
SELF            # definitional exact-self reference

SAFETY=
UNKNOWN         # unless independently established

EPISTEMIC=
OBSERVED_SOURCE

DELTA_GSTAR_FROM_PREDECESSOR=
NOT_COMPUTED_NO_COMPARABLE_PREDECESSOR

ORIGIN_RELATIVE_GSTAR_DISPLACEMENT=
0_BY_DEFINITION
```

This avoids converting "the source equals itself" into an unsupported assertion that the source is scientifically safe/correct.

## 7. Mathematical correction 2 — pairwise tolerance is not an equivalence relation

For a pairwise tolerance rule:

[
x\sim_{\epsilon}y
\iff
|x-y|\le\epsilon,
]

reflexivity and symmetry hold, but transitivity generally fails.

Example:

[
x=0,\quad y=0.75,\quad z=1.5,\quad \epsilon=1
]

gives:

[
x\sim y,\qquad y\sim z,\qquad x\not\sim z.
]

Therefore a generic pairwise tolerance rule MUST NOT create a mathematical `EquivalenceClassFCO`.

### 7.1 Partition / class mode

A rule that defines a true partition/equivalence relation may create:

```
EquivalenceClassFCO
```

Examples include a deterministic, versioned bin/partition rule with non-overlapping boundary semantics.

### 7.2 Pairwise tolerance mode

A pairwise tolerance rule creates:

```
CompatibilityComparisonFCO
```

or:

```
WithinEnvelopeComparisonFCO
```

It records a relation between the two referenced observations and does not imply transitive class membership.

### 7.3 Fixed-reference standard mode

A frozen standard (G_v) may define:

[
\operatorname{Accept}(x\mid G_v)
]

meaning:

> observation (x) satisfies the acceptance policy of version (v) of standard (G).

It does NOT mean every two observations accepted by (G_v) are mutually equivalent.

## 8. MSM-AIS state machine

The Mechanical Scientific Method for Artificial Infinite Systems is the governed process:

```
SOURCE / OBSERVATION
    ↓
exact atomization
    ↓
ContentFCO + OccurrenceFCO
    ↓
typed FCG context
    ↓
question / hypothesis
    ↓
preregistration
    ↓
frozen input / policy
    ↓
execution
    ↓
new observation
    ↓
comparison
    ↓
Anticube companion state
    ↓
G*/DeltaG* state where COMPARABLE
    ↓
claim decision
    ↓
breakpoint / MMR custody
    ↓
successor FCG state
```

MSM-AIS preserves:

[
\text{identity}
\neq
\text{custody}
\neq
\text{interpretation}
\neq
\text{scientific correctness}
\neq
\text{causality}.
]

## 9. Vithia as governed query/context layer

Vithia does not choose a truth path.

For a downstream question (q_t), define a bounded materialization operator:

[
P_t
=
\Pi_{\phi}
(\mathcal F_t,q_t,A_t,G_t^*,U_t),
]

where (phi) is a versioned context-selection policy.

Candidate relevance can depend on:

[
\boxed{
\rho_i(t)
=
f_{\phi}\left(
\Delta C_i,
\Delta O_i,
\Delta A_i,
\Delta G_i^*,
\Delta E_i,
U_i
\right)
}
]

where:

- (Delta C_i): exact content changed/not changed;
- (Delta O_i): occurrence/context change;
- (Delta A_i): Anticube companion-state change;
- (Delta G_i^*): comparable contextual-state displacement;
- (Delta E_i): relevant FCG edge/relationship change;
- (U_i): uncertainty.

This expression is a **preregistered hypothesis form**, not a measured or canonical private scoring formula.

Important consequence:

```
same content hash
+
new contextual state
=
potentially relevant again
```

and:

```
same content hash
+
unchanged relevant context
+
no challenge
=
candidate pointer-only reuse / omission from S1 materialization
```

## 10. Emergent path state

A Golden Path is not written into an atom and is not prescribed in advance.

Let (mathcal A_t) be the set of currently admissible candidate paths and (P_t(\Gamma)) a versioned path distribution.

A candidate selector may be:

[
\Gamma_t^*
=
\operatorname*{arg\,max}_{\Gamma\in\mathcal A_t}
P_t(\Gamma),
]

subject to explicit tie, uncertainty, abstention, and admission rules.

```
highest-weight path
!=
scientifically true path
```

The path distribution is a derived state that may change when new evidence, challenge, failure, or successor observations are admitted.

## 11. Priority / novelty claim ceiling

This baseline establishes a **timestamped public disclosure of this particular integrated formulation**.

It does NOT establish the absolute proposition "nobody in history did this first."

Allowed baseline wording:

> To our knowledge, and subject to continuing prior-art review, the surveyed systems do not combine exact content/occurrence identity, immutable successor interpretations, typed scientific provenance, a self/non-self × safe/non-safe Anticube companion state, versioned comparable contextual-state displacement (G*/DeltaG*), append-only Merkle/MMR custody, and adaptive context materialization between deterministic evidence compilation and a downstream decision system within one closed-loop Mechanical Scientific Method for Artificial Infinite Systems.

Forbidden wording:

```
"We invented System 0."
"We invented System 1."
"Merkle trees are novel."
"Prompt compression is novel."
"No prior system does anything similar."
"DeltaG* is physical Gibbs free energy."
"Anticube has been empirically validated for all domains."
```

## 12. Licensing / rights boundary

No repository-wide `LICENSE` file was present in the frozen `publication/v0.1.0` predecessor at preparation time. This successor therefore does **not** silently apply or change a software/content license.

A public timestamp and a public license perform different functions:

- commit/DOI/publication timestamps provide evidence of public disclosure;
- a license grants reuse permissions within its legal scope;
- licensing does not prove absolute technical priority or inventorship.

Before release, code, manuscript, figures, datasets, and third-party components MUST receive an explicit scope-aware rights matrix.

No private key is distributed. No SIGNED state is asserted without verified signing.

## 13. Current claim state

```
MSM_AIS_FORMAL_BASELINE=
DEFINED_SUCCESSOR

DELTA_GSTAR_GENESIS_CORRECTION=
DEFINED

ORIGIN_RELATIVE_GSTAR_DISPLACEMENT=
DEFINED

PAIRWISE_TOLERANCE_NONTRANSITIVITY_FIX=
DEFINED

ANTICUBE_ORIGIN_SAFETY=
UNKNOWN_UNLESS_ESTABLISHED

SYSTEM0_EXTERNAL_TERM_PRIORITY=
NOT_CLAIMED

VITHIA_S0_ROLE=
DETERMINISTIC_CONTEXT_COMPILER

SYSTEM1_ROLE=
DOWNSTREAM_DECIDER

ADAPTIVE_ANTICUBE_DELTAGSTAR_CONTEXT_SELECTION=
PROPOSED_TO_PREREGISTER

ABSOLUTE_FIRST_IN_FIELD=
NOT_CLAIMED

TIMESTAMPED_PUBLIC_INTEGRATION_BASELINE=
THIS_SUCCESSOR_COMMIT
```
