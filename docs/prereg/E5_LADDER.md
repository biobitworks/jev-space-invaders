PROJECT=VITHIA_0_VITA_1
TASK=E5_OPENJEV_VS_VITHIA_SPACE_1P_2P_LADDER
HOST=magicSTUDIObox
EXECUTE_NOW=YES (after the freezes below)

PROPOSED ≠ IMPLEMENTED ≠ EXECUTED ≠ OBSERVED ≠ SUPPORTED.
Preserve FAILED / NULL / NEGATIVE / PARTIAL / ABSTAIN / DEFERRED / NOT_TESTED / NOT_COMPUTED.
Do not rewrite history. Do not modify any file that is an atom of an existing breakpoint.
New functionality goes in NEW files only.

============================================================
0. RECOVER AND ISOLATE
============================================================

Repo: biobitworks/jev-space-invaders   Branch: vithia-space
Expected predecessor (verify, do not trust):
  HEAD=0a86efd7fbc105af8558f560b6e0b67d21716769
  LATEST_BP=UFA-JEV-BP-0026 (E4C panel, BLOCKED_OR_UNDERPOWERED)
  MMR_SIZE=26  MMR_ROOT=c47a1df560aca5d2885aa95e3edbec5c7d62fc9ddc2aafa3580f5f94b3be6235

The Studio checkout on publication/v0.1.0 must not be touched.
Use a separate worktree (e.g. ../jev-vithia) on vithia-space; fast-forward only.
Run: pytest, scripts/secret_scan.py, scripts/verify_breakpoints.py, scripts/verify_episode_mmr.py.
Stop on any failure. Single writer: magicPRObox must not push while this runs.

============================================================
1. DEFINITIONS (freeze these; they prevent a type error)
============================================================

"vithia-space" is NOT a decider. System 0 compiles context; System 1 decides.
Therefore the two PLAYERS compared here are the SAME System-1 model under two context contracts:

  OJ  = OpenJev(A0_RAW)          perception state only
  VS  = OpenJev(A5_VITA01_FULL)  same state + 0-Vita-1 context
                                  (history, public Anticube labels, public path distribution;
                                   A3 governed ΔG* is NOT_COMPUTED and absent)

Both: provider=openjev, NON_TYPESAFE_JEV, NON_COUNTED_FOR_TYPESAFE_PERFORMANCE.
Neither packet may contain recommended_action / recommended_move / golden_action / best_action.
If TypeSafe JEV later becomes available, the same ladder may be repeated as a SEPARATE successor
with JEV as System 1; never mix providers inside one matchup.

Any claim reads: "Vita01 context vs raw state, holding the decider fixed" — not
"Vithia beats OpenJev".

============================================================
2. OPENJEV RUNTIME GATE
============================================================

Use the existing tooling:
  pip install -r requirements-openjev.txt
  python scripts/openjev_runtime.py download   # pinned revisions, local SHA-256 of every artifact
  python scripts/openjev_runtime.py serve      # loopback port 8765+ (never 3000), 7 checks, SETUP_SMOKE

Continue only if evidence/openjev/RUNTIME_MANIFEST.json has OPENJEV_LOADED=YES.
Commit + push that receipt (its own commit). Record host RAM, chip, engine versions.
Measure and record per-call latency on 20 SETUP_SMOKE calls (synthetic, NON_EXPERIMENTAL) so
the episode time budget below can be set BEFORE any scientific call.

============================================================
3. E4B FIRST (already specified; do not redesign)
============================================================

  python scripts/run_e4b.py --stage prereg  --push --branch vithia-space
  python scripts/run_e4b.py --stage execute --push --branch vithia-space

E4B quality remains NULL / METRIC_NOT_DISCRIMINATING / NOT_A_PRIMARY_ENDPOINT.
E4C quality lane is BLOCKED_OR_UNDERPOWERED (BP-0026): no action-quality claim anywhere below
may cite it.

============================================================
4. E5-1P: OJ vs VS, single player (ALE)
============================================================

Environment: ALE/SpaceInvaders-v5 via src/envcfg.make_env (frameskip-1 + RepeatActionMaxPool(4)).
Action ontology: ActionOntologyFCO_ALE = NOOP, FIRE, RIGHT, LEFT, RIGHTFIRE, LEFTFIRE.

Implement NEW file experiments/e5_episodes.py with an episode runner that, per decision:
  perception_v1 state → arm context (reuse experiments/e4b_ablation helpers for history,
  anticube, path_distribution; do not edit that file) → OpenJevDecider.decide_body → env.step,
and writes per-decision EPISODE_LEAF_V1 Merkle leaves + episode MMR root (same rule as
src/harness.py), trace file, and measured latency split into S0 / serialize / decider.

Matchups: OJ and VS, seeds 1-5 each (10 episodes).
Order: interleave by seed (OJ s1, VS s1, OJ s2, ...) to spread thermal/time drift.
Cap: MAX_DECISIONS per episode frozen from the Section 2 latency measurement so that the whole
E5 ladder fits the stated wall-clock budget; a capped episode is truncated=true, not dropped.

Endpoints (prereg):
  primary     score per episode, paired by seed (Wilcoxon signed-rank, VS vs OJ)
  secondary   decisions survived, lives lost, fallback rate, valid-action rate,
              latency p50/p95 per decision, NET_TIME_SAVED (OJ_total − VS_total per decision)
  descriptive action distribution, probability entropy (if returned; else NOT_AVAILABLE)
With n=5 pairs, the minimum attainable two-sided p is 0.0625: the prereg must state that
SUPPORTED is impossible at α=0.05 and report effect sizes with bootstrap CIs; claim state for
the test is FAIL_TO_REJECT_H0 or DESCRIPTIVE_ONLY, never upgraded.

Output: its own dataset S01_E5_1P_RESULTS_V1 under data/s01/ + receipts under results/vita01/.
Do NOT append these to root results.json unless labelled provider=openjev (non-JEV); judges'
counted runs remain TypeSafe-only.

============================================================
5. E5-2P: PettingZoo two-player ladder
============================================================

Environment: pettingzoo.atari.space_invaders_v2 (Parallel API), agents first_0, second_0.
Action ontology: ActionOntologyFCO_PZ = NOOP, FIRE, UP, RIGHT, LEFT, DOWN.
This is NOT the ALE ontology. Byte 2 = UP here, RIGHT in ALE (TYPE_ERROR_T8).
Write a NEW 2P question with PZ criteria; never reuse the ALE MOVE_QUESTION.

ROM / licence gate (fail closed):
  multi-agent-ale-py does not ship the Space Invaders ROM (BP-0005 runtime freeze recorded
  ROM=NOT_PRESENT, licence GPL for the runtime). If obtaining the ROM requires accepting a licence
  (e.g. AutoROM --accept-license), STOP and ask Byron; do not accept on his behalf.
  If a ROM is supplied, record its SHA-256/MD5 and provenance in a successor runtime dataset,
  and verify it matches the ALE-bundled space_invaders.bin identity where comparable.

2P perception (NEW file src/perception_2p.py): per agent, "own ship" vs "opponent ship" by the
observed colour for that seat (P1 green 50,132,50; P2 orange 162,134,56 in ALE rendering — verify
on PettingZoo frames before freezing; if colours differ, record and use the observed ones).
Each agent's context contains only what its own observation shows; do not leak one agent's
private context into the other's packet.

Matchups (seeds 1-5 each):
  M1  VS vs VS
  M2  VS vs OJ   and   M2' OJ vs VS   (seat swap; both required — seat is a confound)
  M3  OJ vs OJ
= 20 episodes. Same MAX_DECISIONS cap. Interleave matchups by seed.

Row schema: schemas/daisy/daisy_2p_row_v1.json (vita_action, opponent_action, vita_outcome,
opponent_outcome, relative_payoff). Never write 2P rows with the 1P schema.

Endpoints:
  primary     relative payoff (VS score − OJ score) in M2+M2', paired by seed and seat
  secondary   per-seat score, lives, fallback/valid-action rates, latency per agent
  controls    M1 and M3 give the seat-advantage and self-play baselines; report both
Small-n caution as in Section 4.

2P is a SUCCESSOR experiment. It is not Pilot evidence and does not enter root results.json.

============================================================
6. GOVERNANCE PER STAGE
============================================================

Before any scientific call, create and push, in order (numbers allocated dynamically):
  a. E5 prereg breakpoint: this protocol text, arm definitions, ontologies, questions,
     seeds, order, MAX_DECISIONS, endpoints, tests, stop rules, runtime manifest, code atoms.
  b. (2P only) runtime successor breakpoint with ROM/licence identity.
After each completed block (1P; each 2P matchup):
  result dataset + ExperimentReceipt → breakpoint → MMR append → verify_breakpoints →
  verify_episode_mmr → commit → push → fetch → confirm remote reachability.
SIGNATURE_STATE=NOT_SIGNED unless actually signed in Byron's boundary.

============================================================
7. STOP CONDITIONS
============================================================

OPENJEV_LOADED != YES; resident process dies mid-block (seal partial as PARTIAL, do not rerun
silently); frozen atom changed; ROM licence acceptance required; push rejected / remote moved;
disk < 5 GB free; any packet containing a decision field; ALE and PZ ontologies conflated;
wall-clock budget exceeded (seal what is complete, mark the rest DEFERRED).

============================================================
8. REPORT
============================================================

REMOTE_HEAD / WORKTREE / OPENJEV_LOAD_STATE / ENDPOINT / MEASURED_CALL_LATENCY
E4B: freeze BP, result BP, per-arm NET_TIME_SAVED, claim states
E5-1P: BP ids, per-seed scores OJ vs VS, effect size + CI, claim state
E5-2P: ROM gate state, per-matchup per-seat scores, relative payoff, seat effect, claim states
MMR_SIZE / MMR_ROOT / VERIFY states
NOT_TESTED: TypeSafe JEV, LLM baseline, governed ΔG*
Do not report any number that was not produced by an executed, sealed run.
