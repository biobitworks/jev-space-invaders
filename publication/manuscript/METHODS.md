# Methods - frozen v0.1.0 candidate

## System boundary

Vithia 0-Vita-1 separates exact evidence identity from contextual interpretation and downstream decisions. The public computational path is

\[
E_t \xrightarrow{S_0} C_t \xrightarrow{\Pi} P_t \xrightarrow{S_1} D_t
\xrightarrow{\mathrm{world}} O_{t+1} \xrightarrow{S_0} C_{t+1},
\]

where \(E_t\) is source evidence, \(S_0\) is Vithia-S0, \(C_t\) is a finite VitaState in persistent VitaContext, \(\Pi\) constructs a bounded ContextPacket \(P_t\), \(S_1\) is a downstream decider, \(D_t\) is a DecisionReceipt, and \(O_{t+1}\) is a subsequently observed transition. In v0.1.0, experiments E0-E3 test the evidence/context substrate and E4A freezes a partially observed game dataset; no E4A downstream decider call is admitted.

Vithia-S0 is a context compiler rather than a decision model. This distinction is enforced by public schemas and type tests. The same source atom may acquire successor ContextFCOs, but its exact source identity is not rewritten. The protocol therefore maintains

\[
\mathrm{identity} \neq \mathrm{meaning}, \qquad
\mathrm{prediction} \neq \mathrm{observation}.
\]

## Canonicalization and FCO identity

Governed artifacts are committed using exact byte length and SHA-256 identity. Hashes are used for identity/deduplication only; no semantic similarity, correctness, truth, or causality is inferred from hash values. An FCO atom record contains a relative path, kind, group, byte count, SHA-256 digest, location state, and deterministic FMO leaf. Content identity and occurrence/context identity remain distinct.

## Typed FCG relationships

The Fractal Context Graph (FCG) represents declared typed relationships among governed objects. Relevant public relationship types include DERIVED_FROM, CONTEXTUALIZED_BY, EXECUTED_WITH, OBSERVED_AS, COMPARED_WITH, EVIDENCE_FOR, REPLAY_OF, and SUPERSEDES. An edge records a declared relationship; it is not by itself causal evidence.

## Breakpoint Merkle roots

For each atom, the project computes

\[
L=\operatorname{SHA256}(
\mathrm{FMO\_LEAF\_V1} \Vert 0
\Vert path \Vert 0 \Vert bytes \Vert 0 \Vert sha256).
\]

Leaves are grouped by declared group. Within each group, adjacent nodes are combined as

\[
N=\operatorname{SHA256}(
\mathrm{FMO\_NODE\_V1} \Vert 0
\Vert left \Vert 0 \Vert right),
\]

duplicating the final digest at odd levels. Group roots are domain-separated and sorted before construction of the breakpoint root. The construction is project-specific; Certificate Transparency is cited only as background for independently auditable Merkle structures, not as an assertion that this implementation is RFC 9162 Certificate Transparency.

## Ordered MMR custody

Each breakpoint is appended to a project MMR with a domain-separated leaf committing sequence number, breakpoint identifier, breakpoint root, and exact breakpoint-file SHA-256. Peaks of equal height merge, and remaining peaks are bagged right-to-left under a separate domain. The verifier recomputes atom hashes, breakpoint roots, MMR leaves, and the final MMR root without trusting stored roots.

Merkle/MMR inclusion establishes identity, inclusion, and ordered custody only. It does not establish scientific correctness or truth. The publication uses a second publication-specific breakpoint/MMR namespace. Scientific MMR leaves are referenced but never copied as publication MMR leaves.

## Continuous equivalence

Continuous measurements preserve exact raw identity. Two different raw byte strings never intentionally share a content hash merely because they are numerically close. Contextual equivalence is instead represented by a frozen EquivalenceRuleFCO and a derived class identity.

\[
\text{exact identity} \neq \text{contextual equivalence}
\neq \text{statistical similarity}.
\]

Rules require version, units, uncertainty method, and boundary semantics. Reclassification creates a successor ClassificationFCO rather than editing historical classifications.

## Scientific-state vocabulary

Integrity gates use PASS/FAIL. Scientific claims use SUPPORTED, NOT_SUPPORTED, FAIL_TO_REJECT_H0, NULL, NEGATIVE, PARTIAL, ABSTAIN, NOT_TESTED, or UNKNOWN as applicable. PROPOSED, IMPLEMENTED, EXECUTED, OBSERVED, and SUPPORTED are not interchangeable.

## Mechanical Scientific Method execution

The experimental chain is question -> hypothesis -> preregistration -> input freeze -> execution -> observation -> analysis -> claim decision -> breakpoint -> independent verification -> successor. Exploratory rehearsals remain separate from post-rehearsal prospective confirmatory executions. Corrections are successor states; frozen predecessors are never rewritten.

## E0 - exact addressability

E0 evaluates exact reversible addressing across five deterministic state spaces. It tests round-trip recovery, address collision, content-ID collision, separation between address and content hash, and the continuous-equivalence contract. Inputs comprise five spaces with 2,002 states each (10,010 rows total).

## E1 - elementary cellular automata

E1 evaluates all 256 elementary cellular-automaton rules across four initial-condition classes and five observation/corruption regimes. Candidate compatible rule sets are updated as observations accumulate. CellPyLib 2.4.0 provides an independently implemented comparison on specified rule/initial-condition combinations. The preregistered H1d threshold remains 90%; misses are not repaired after execution. H1e and its prospective successor H1e_v2 retain their original null-decision rules.

## E2 - Conway-style context and history

E2 evaluates whether immutable lower-level cell evidence can support distinct higher-order contextual interpretations. It records one-cell perturbations, masked observations, persistent-object classifications, and matched CORRECT_HISTORY, SHUFFLED_HISTORY, and NO_HISTORY controls while holding the current atom constant where possible.

## E3 - hidden deterministic worlds

E3 uses Minesweeper states to separate deterministic world mechanics from epistemic uncertainty. A project kernel is compared against a separate PySAT/Minisat22 oracle implementation. States above the kernel component cap are ABSTAIN_SIZE_LIMIT and are excluded from the oracle-agreement claim rather than labeled PASS or FAIL. For eligible unknown cells, expected information gain is compared with realized information gain and a deterministic random-cell comparator.

## E4A - frozen partially observed game state

E4A uses ALE/SpaceInvaders-v5 as the single-player environment. The snapshot dataset contains 96 replay-verified states balanced between bomb-positive and bomb-negative strata. E4A is input freeze only. No JEV, OpenJEV, System One adapter, Liquid, Ollama/Ollarma, or other downstream decider result is part of v0.1.0.

ALE provides the Atari evaluation environment; PettingZoo is retained as a distinct future two-agent successor environment rather than conflated with ALE single-player semantics.

## Replay levels

Replay levels are ordinal descriptive labels: Level 0, source recoverable; Level 1, environment recoverable; Level 2, same frozen inputs/seeds but output bytes differ; Level 3, equivalent under an explicitly frozen tolerance/equivalence rule; Level 4, byte-identical deterministic replay. A lower replay level is preserved as evidence rather than upgraded retrospectively.

## Statistics

Confirmatory hypothesis tests are those frozen before confirmatory execution. A separate post-confirmatory secondary-analysis successor derives confidence intervals and effect sizes from frozen outputs without mutating original claim states.

Secondary analysis uses deterministic NumPy bootstrap resampling with seed 20260927, 10,000 resamples, and percentile 95% intervals. E1/H1d additionally receives a Wilson binomial interval. E1/H1e and H1e_v2 receive Cliff's delta and bootstrap median-difference intervals. E2 history controls are matched by scene and time. E3 max-information-gain and random-question realized gains are paired by frozen state.

SciPy and NumPy provide numerical/statistical infrastructure. Statistical calculations are evidence about the frozen datasets, not a mechanism for changing preregistered claim decisions.

## Evidence-level boundary

All current E0-E4A evidence is SIMULATED. No result in v0.1.0 is promoted to in-vitro, in-vivo, clinical, or causal biological evidence. Translation to other evidence levels is a future protocol use case and remains NOT_TESTED.

## Private implementation boundary

Private System-0 mathematics, private Anticube mathematics, Golden-Corridor internals, and the private DeltaGStar formula/coefficients are not disclosed by this release. DeltaGStar is NOT_COMPUTED in the v0.1.0 evidence chain. No surrogate is presented as DeltaGStar.

## Reproducibility boundary

The scientific chain is committed in governance/MMR_LEDGER.json; publication artifacts use governance/publication/MMR_LEDGER.json. Every public numerical result in the manuscript must be generated from governed receipts or frozen datasets. Manual numerical transcription is prohibited for figure/table generation.
