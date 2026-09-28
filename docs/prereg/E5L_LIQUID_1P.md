# E5L — LiquidAI raw-state vs Vita01-context 1P successor

State before prereg: PROPOSED / IMPLEMENTED_ONLY.

Question: holding System-1 fixed, how does 0-Vita-1 public context change LiquidAI action selection, episode score, survival and latency versus raw perception state?

System-1 identity is frozen by evidence/liquid/RUNTIME_MANIFEST.json. This successor uses the already-present official LiquidAI/LFM2.5-1.2B-Instruct-GGUF Q4_0 artifact. It is NOT the abandoned/unfrozen MLX-8bit candidate.

Arms:
- LQ_RAW = LiquidAI(A0_RAW), perception state only.
- LV_VITA01 = LiquidAI(A5_VITA01_FULL), same state plus history, public Anticube labels and public path distribution.
- governed DeltaG* is NOT_COMPUTED and absent.

Neither packet may contain recommended_action, recommended_move, golden_action or best_action. The decider is the same exact model/runtime in both arms.

Environment: canonical ALE/SpaceInvaders-v5 through src/envcfg.make_env.
Seeds: 1,2,3,4,5.
Order: interleave by seed LQ_RAW then LV_VITA01.
MAX_DECISIONS is frozen in E5L_PREREG_CONFIG.json before scientific calls. Capped episodes remain truncated=true.

Primary endpoint: paired episode score LV_VITA01 - LQ_RAW by seed. With n=5 pairs, minimum attainable two-sided Wilcoxon p is 0.0625, therefore SUPPORTED at alpha=.05 is impossible. Report effect size and deterministic bootstrap CI; claim is FAIL_TO_REJECT_H0 or DESCRIPTIVE_ONLY.

Secondary: decisions, lives lost, fallback/valid action rates, latency p50/p95, mean total decision time and NET_TIME_SAVED = LQ_RAW total - LV_VITA01 total.

Probabilities, confidence and entropy are NOT_AVAILABLE for this Ollama structured-output adapter; do not fabricate them.

E4C remains BLOCKED_OR_UNDERPOWERED at BP-0026 and is not used to make action-quality claims.

Resilience: after prereg, each completed seed pair is written, checkpointed, committed and pushed before the next seed begins. Final analysis is a separate breakpoint after all five pairs exist.

Labels: provider=liquid, NON_TYPESAFE_JEV, NON_OPENJEV, NON_COUNTED_FOR_TYPESAFE_PERFORMANCE.

