# MSM-AIS Priority, Terminology, and License-Scope Matrix v0.2

**Status:** PUBLIC DISCLOSURE BASELINE — RIGHTS NOT EXPANDED  
**Publication predecessor:** `publication/v0.1.0@2ce9cd8a9b2c3bba63515a7e7eb6cb072f3a8a4c`

## 1. Purpose

Establish a precise, timestamped baseline for the specific MSM-AIS integration without claiming priority over established terms or components.

This document is evidentiary/project governance material, not legal advice and not an assertion that a repository timestamp alone proves patent inventorship, statutory novelty, or worldwide priority.

## 2. External terminology that predates this successor

### System 0

Chiriatti, Ganapini, Panai, Ubiali, and Riva published **"The case for human-AI interaction as system 0 thinking"** in *Nature Human Behaviour* in 2024.

DOI:

```
10.1038/s41562-024-01995-5
```

That System 0 is described as an artificial/informational layer that shapes the inputs available to human System 1/System 2 cognition.

A 2025 follow-up, **"System 0: Transforming Artificial Intelligence into a Cognitive Extension"**, further develops that cognitive-extension framing.

DOI:

```
10.1089/cyber.2025.0201
```

Therefore:

```
CLAIM_VITHIA_INVENTED_TERM_SYSTEM_0=FORBIDDEN
```

### System 1

System 1/System 2 dual-process terminology predates this project. Vithia's use of a downstream `S1` role is an implementation-role label and MUST NOT be framed as invention of cognitive System 1.

## 3. Vithia-specific distinction

The project-specific architecture is:

```
VITHIA-S0
deterministic evidence/context compiler

        ↓

MSM-AIS contextual governance
Anticube + comparable G*/DeltaG*
+ typed FCG + uncertainty
+ bounded projection policy

        ↓

DOWNSTREAM S1
model/agent decision

        ↓

world / experiment

        ↓

successor observation
```

The priority candidate is not the existence of a pre-processing stage. It is the integrated, governed closed-loop formulation in which:

1. exact content and occurrence identity remain independently addressable;
2. source evidence is not rewritten by later interpretations;
3. Anticube provides an explicit self/non-self × safe/non-safe companion state with UNKNOWN;
4. G*/DeltaG* is restricted to versioned comparable contextual states;
5. Merkle/MMR preserves identity/order/custody rather than truth;
6. Vithia materializes a bounded local FCG projection for a downstream decider;
7. the world produces a successor observation;
8. MSM admits/challenges/abstains and appends a successor rather than modifying history.

## 4. Priority claim states

### Allowed

```
TIMESTAMPED_PUBLIC_DISCLOSURE=
YES, via exact Git commit(s)

ABSOLUTE_FIRST_IN_FIELD=
NOT_ESTABLISHED

PRIOR_ART_REVIEW=
ONGOING

NOVELTY_CANDIDATE=
INTEGRATION_AND_OPERATIONAL_COUPLING
```

Allowed wording:

> This repository establishes a timestamped public baseline for our MSM-AIS formulation integrating immutable FCO/FCG evidence state, Anticube companion classification, versioned comparable G*/DeltaG* state, append-only cryptographic custody, and bounded Vithia context materialization between deterministic context compilation and downstream decision systems.

Also allowed:

> To our knowledge, subject to continuing prior-art review, we have not identified a surveyed system that combines all of these functions under one closed-loop scientific-state protocol.

### Forbidden

```
"We invented System 0."
"We invented System 1."
"We were the first people ever to use provenance for agents."
"We were the first to use Merkle trees for science."
"No prior art exists."
"This commit legally proves patent priority."
```

## 5. Nearest-component prior art / comparison classes

The publication successor should compare at least:

```
System 0 cognitive-extension literature
dual-process System 1/System 2 literature
content-addressed Merkle DAG systems
W3C PROV
Trusty URIs / nanopublication-style immutable references
RO-Crate / research-object provenance
event sourcing / immutable event projection
replay systems such as StarCraft II
LLMLingua / LongLLMLingua context compression
standard uncertainty propagation / metrology
```

For every related-work row, record:

```
PRIOR_ART_COMPONENT
NEAREST_ANALOG
OUR_DIFFERENCE
EVIDENCE_FOR_DIFFERENCE
CLAIM_CEILING
```

## 6. Current repository license state

At the frozen `publication/v0.1.0` predecessor:

```
ROOT_LICENSE_FILE=NOT_FOUND
THIRD_PARTY_NOTICES=FOUND
```

The predecessor therefore did not expose a repository-wide license file that this successor can safely inherit as a global rights statement.

This successor DOES NOT add a repository-wide license and DOES NOT silently relicense code, data, figures, or third-party materials.

## 7. Scope-aware licensing recommendation

Licensing and priority evidence are different mechanisms.

A license controls permissions to reuse a work. A commit/DOI/publication records disclosure/provenance. Neither alone proves absolute first-in-field status.

### 7.1 Manuscript / original figures

Candidate only, requiring operator approval before application:

```
CC BY-NC-ND 4.0
```

If selected, this license permits sharing the unadapted material for noncommercial purposes with attribution. Public distribution of adaptations is not permitted under the ND condition.

Creative Commons 4.0 licenses do not themselves license patent or trademark rights.

STATE:

```
MANUSCRIPT_LICENSE_CANDIDATE=CC_BY_NC_ND_4_0
MANUSCRIPT_LICENSE_APPLIED=NO
OPERATOR_APPROVAL_REQUIRED=YES
```

### 7.2 Source code

Creative Commons licenses are not silently applied to software here.

STATE:

```
CODE_LICENSE_APPLIED=NO
CODE_REUSE_POLICY=UNRESOLVED
```

Until an explicit software license is selected, do not describe the repository as open-source merely because it is publicly viewable.

### 7.3 Evidence / datasets / third-party assets

Each dataset or asset must preserve its source-specific rights state.

The existing third-party notice already records differing upstream licenses and ROM/runtime boundaries.

STATE:

```
THIRD_PARTY_RIGHTS=SOURCE_SPECIFIC
GLOBAL_RELICENSE=FORBIDDEN_WITHOUT_REVIEW
```

## 8. Suggested release/custody sequence

For a future Zenodo/publication successor:

```
1. freeze manuscript bytes
2. freeze supplement bytes
3. freeze figure/table bytes
4. compute exact SHA-256 identities
5. bind claim matrix
6. bind citation audit
7. bind rights/license scope per artifact
8. create publication breakpoint
9. verify Merkle/MMR
10. verify signature if signing is actually performed
11. publish DOI
12. preserve DOI/publication receipt as successor evidence
```

Do not claim SIGNED merely because a public key exists.

## 9. Public baseline record

The baseline should cite both exact commits:

```
FORMAL_BASELINE_COMMIT=
<commit containing MSM_AIS_ANTICUBE_GSTAR_BASELINE_V02.md>

PREREGISTRATION_COMMIT=
<commit containing MSM_AIS_V02_PREREGISTRATION.md>
```

These are content/custody timestamps for this project state.

A later Zenodo DOI should cite these predecessor commits rather than pretending the DOI originated the concepts.

## 10. Current legal/priority claim ceiling

```
PUBLIC_DISCLOSURE_EXISTS=YES
ABSOLUTE_PRIORITY_PROVEN=NO
PATENT_NOVELTY_DETERMINED=NO
PATENT_RIGHTS_LICENSED_BY_CC=NO
TRADEMARK_RIGHTS_LICENSED_BY_CC=NO
SOFTWARE_OPEN_SOURCE_LICENSE_PRESENT=NO
```

If patent protection is contemplated, obtain jurisdiction-specific patent advice before making additional unpublished implementation details public.
