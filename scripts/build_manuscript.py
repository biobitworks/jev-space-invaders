#!/usr/bin/env python3
import json
from pathlib import Path
R=Path(__file__).resolve().parents[1]; P=R/"publication"
M=P/"manuscript"; S=P/"supplement"; M.mkdir(parents=True,exist_ok=True); S.mkdir(parents=True,exist_ok=True)
J=lambda p: json.loads((R/p).read_text())
r={k:J(f"evidence/s01/{v}/EXPERIMENT_RECEIPT.json") for k,v in {"E0":"E0_ADDRESSABILITY","E1":"E1_ECA","E2":"E2_LIFE","E3":"E3_MINESWEEPER"}.items()}
st=J("evidence/statistical_successor/STATISTICAL_ANALYSIS.json"); lock=J("publication/EVIDENCE_LOCK.json"); cm=J("publication/CLAIM_MATRIX.json")
C=lambda e,c: next(x for x in r[e]["claims"] if x["id"]==c)
g1=C("E1","G1"); h1d=C("E1","H1d"); h1e=C("E1","H1e"); h1v=C("E1","H1e_v2"); h2=C("E2","H2d"); h3a=C("E3","H3a"); h3b=C("E3","H3b"); h3c=C("E3","H3c")
title="Vithia 0-Vita-1: A Deterministic Context Protocol for Verifiable Scientific State Transitions"
def fig(name,cap,w=".82"):
    return rf"\begin{{figure}}[H]\centering\includegraphics[width={w}\textwidth]{{../figures/{name}.pdf}}\caption{{{cap}}}\end{{figure}}"
parts=[
r"\documentclass[11pt]{article}",r"\usepackage[margin=.78in]{geometry}",r"\usepackage{graphicx,amsmath,hyperref,float,microtype}",r"\hypersetup{colorlinks=true,allcolors=blue}",
rf"\title{{{title}}}",r"\author{Byron P. Lee\\Biobitworks}",r"\date{v0.1.0 release candidate --- DOI not yet reserved}",r"\begin{document}",r"\maketitle",
r"\begin{abstract}Scientific workflows can conflate evidence with interpretation, prediction with observation, provenance with correctness, and graph connectivity with causality. We present 0-Vita-1, a Vithia protocol separating deterministic context compilation from downstream decisions while preserving typed provenance and append-only custody. Simulated experiments test exact addressability (E0), rule inference under corruption (E1), history-sensitive context (E2), uncertainty over hidden deterministic worlds (E3), and a frozen Space Invaders snapshot set (E4A). E0, E2, and E3 are supported; E1 is partial and retains negative/null outcomes; E4A contains no decider calls. Breakpoint roots and an ordered MMR preserve identity and order, not truth. Each committed state is finite while successor context is indefinitely extensible.\end{abstract}",
r"\section{Introduction}% CLAIM:ARCH::S0_ROLE"+"\n0-Vita-1 treats scientific type errors as a protocol problem: exact evidence identity remains separate from contextual interpretation, and Vithia-S0 context compilation remains separate from System-1 decision-making.",
r"% CLAIM:GOV::MMR24"+"\nHashes identify exact bytes; typed FCG edges declare relationships; breakpoint roots commit governed artifact sets; and an ordered MMR commits their sequence. These integrity mechanisms do not establish scientific truth.",
r"\section{Formal architecture}",
r"\[E_t\xrightarrow{S_0}C_t\xrightarrow{\Pi}P_t\xrightarrow{S_1}D_t\xrightarrow{\mathrm{world}}O_{t+1}\xrightarrow{S_0}C_{t+1}.\]",
"Vithia-S0 compiles source evidence into finite VitaState context. A bounded ContextPacket is projected for one downstream question; a subsequent observation creates successor evidence.",
fig("F1_architecture","0-Vita-1 evidence, context, decision, and successor loop",".96"),
r"\[\mathrm{identity}\neq\mathrm{meaning},\quad\mathrm{custody}\neq\mathrm{correctness},\quad\mathrm{prediction}\neq\mathrm{observation}.\]",
r"\section{Mechanical Scientific Method}"+"\nThe execution chain is question, hypothesis, preregistration, input freeze, execution, observation, analysis, claim decision, breakpoint, independent verification, and successor. Historical failures, nulls, and abstentions remain addressable.",
fig("F2_custody","FCO, typed FCG, breakpoint, and ordered MMR custody",".90"),
r"\section{Experiment ladder}"+fig("F3_experiment_ladder","Progressive experimental burden from identity to partial observation",".80"),
r"E1 uses CellPyLib as an independent cellular-automaton implementation comparison \cite{cellpylib}; E3 uses a separately implemented SAT-oracle lane based on PySAT \cite{pysat}; E4A uses the Arcade Learning Environment as the single-player partially observed game substrate \cite{ale}.",
r"\section{Results}",
r"\subsection{E0: exact addressability}% CLAIM:E0_ADDRESSABILITY::H0a"+"\nE0 is SUPPORTED. Across 10,010 rows the receipt records zero round-trip failures, zero address collisions, zero content-ID collisions, and zero address/hash-equality rows. Replay is Level 4.",
r"\subsection{E1: rule inference}% CLAIM:E1_ECA::H1d",
f"The independent comparison agreed on {g1['cross_check']['cells']:,} cells with zero mismatches. E1 remains PARTIAL: H1d rank-1 fraction {h1d['fraction_rank1']:.3f} is below the 0.90 threshold; Wilson 95\\% CI [{st['E1']['H1d']['wilson95'][0]:.3f},{st['E1']['H1d']['wilson95'][1]:.3f}]. H1e (p={h1e['p']:.3g}) and H1e-v2 (p={h1v['p']:.3f}) both FAIL\\_TO\\_REJECT\\_H0.",
fig("F4_e1_outcomes","E1 H1d and the preregistered threshold",".58"),
r"\subsection{E2: history-sensitive context}% CLAIM:E2_LIFE::H2d",
f"E2 is SUPPORTED. Correct-history accuracy {h2['accuracy_correct_history']:.3f}, shuffled-history {h2['accuracy_shuffled_history']:.3f}, and no-history unknown rate {h2['unknown_rate_no_history']:.3f}. There are {h2['same_current_atom_different_context']} same-current-atom/different-context cases. Secondary matched accuracy delta {st['E2']['H2d']['mean_accuracy_difference_correct_minus_shuffled']:.3f}, 95\\% bootstrap CI [{st['E2']['H2d']['bootstrap95_accuracy_difference'][0]:.3f},{st['E2']['H2d']['bootstrap95_accuracy_difference'][1]:.3f}].",
fig("F5_e2_history","E2 history manipulation",".58"),
r"\subsection{E3: hidden deterministic worlds}% CLAIM:E3_MINESWEEPER::H3a",
f"E3 is SUPPORTED with abstention. Kernel and SAT oracle agree on {h3a['agree_cells']:,} eligible cells with zero disagreements; {h3a['abstain_size_limit_states']} states ({h3a['abstain_size_limit_cells']:,} cells) are ABSTAIN\\_SIZE\\_LIMIT.",
r"% CLAIM:E3_MINESWEEPER::H3b",
f"For {h3b['pairs']} pairs, max-EIG realized gain is {h3b['mean_gain_max_eig']:.4f} bits versus {h3b['mean_gain_random']:.4f} random (p={h3b['p']:.4g}); secondary paired delta {st['E3']['H3b']['mean_paired_gain_difference']:.3f} bits, 95\\% CI [{st['E3']['H3b']['bootstrap95_mean_difference'][0]:.3f},{st['E3']['H3b']['bootstrap95_mean_difference'][1]:.3f}]. Replay remains Level 2.",
fig("F6_e3_information_gain","E3 information-directed versus random questions",".58"),
r"\subsection{E4A: frozen partial observation}% CLAIM:LIMIT::E4A"+"\nE4A freezes 96 replay-verified snapshots balanced 48/48 between bomb-positive and bomb-negative strata. It is INPUT\\_FROZEN\\_NO\\_DECIDER\\_CALLS. No JEV, OpenJEV, Liquid, or Ollama/Ollarma utility claim follows.",
fig("F7_e4a_pipeline","E4A boundary; downstream System-1 is not tested",".86"),
r"\section{Post-confirmatory statistics}% CLAIM:STAT::SECONDARY",
f"Secondary analyses use frozen outputs and do not alter confirmatory states. E3 paired Cohen d-z is {st['E3']['H3b']['paired_cohen_dz']:.3f}; E3 abstention fraction is {st['E3']['abstention']['fraction']:.3f}.",
r"\section{Reproducibility and custody}% CLAIM:GOV::MMR24",
f"The publication evidence lock references {lock['scientific_breakpoint']}, scientific MMR size {lock['scientific_mmr_size']}, root {lock['scientific_mmr_root'][:12]}...{lock['scientific_mmr_root'][-6:]}. The complete root is retained in the governed evidence lock and supplement. Manuscript evolution uses a distinct publication MMR.",
fig("F8_breakpoint_timeline","Ordered scientific breakpoint lineage",".92"),
r"\section{Discussion}The results support a narrow architectural conclusion: exact evidence can remain immutable while deterministic rules produce versioned context and uncertainty remains explicit. Deterministic evidence handling does not imply a deterministic downstream model or world. Artificial Infinite Systems is structural rather than literal: every committed state is finite, while successor states can extend without rewriting predecessors.",
r"\section{Limitations}% CLAIM:LIMIT::DELTAGSTAR"+"\nDeltaGStar is NOT\\_COMPUTED; private DeltaGStar and Anticube mathematics are not disclosed and no surrogate is labeled DeltaGStar.",
r"% CLAIM:LIMIT::CROSSHOST"+"\nCross-host replication is DEFERRED\\_NOT\\_FAILED because magicPRObox was unavailable. E3 is Level-2 replay. Hosted JEV, OpenJEV, System One, Liquid, and Ollama/Ollarma utility are NOT\\_TESTED. All evidence is simulated; biological transfer is NOT\\_TESTED. Signatures are NOT\\_SIGNED.",
r"\section{Conclusion}0-Vita-1 provides a testable boundary between immutable evidence, deterministic context compilation, explicit uncertainty, downstream decisions, and successor observations. v0.1.0 establishes the substrate through E4A while preserving negative, null, partial, abstention, and not-tested states.",
r"\begin{thebibliography}{3}",r"\bibitem{ale} Bellemare et al. The Arcade Learning Environment. JAIR 47 (2013). doi:10.1613/JAIR.3912.",r"\bibitem{cellpylib} Antunes. CellPyLib. JOSS 6(67) (2021). doi:10.21105/joss.03608.",r"\bibitem{pysat} Ignatiev et al. PySAT. SAT 2018. doi:10.1007/978-3-319-94144-8\_26.",r"\end{thebibliography}",r"\end{document}"
]
main="\n".join(parts)+"\n"; (M/"main.tex").write_text(main)
bindings=[]
for i,line in enumerate(main.splitlines(),1):
    if "% CLAIM:" in line:
        cid=line.split("% CLAIM:",1)[1].split()[0]
        ent=next(x for x in cm["entries"] if x["claim_id"]==cid)
        bindings.append({"line":i,"claim_id":cid,"state":ent["state"],"evidence_refs":ent["evidence_refs"]})
(P/"MANUSCRIPT_CLAIM_BINDINGS.json").write_text(json.dumps({"schema":"VITHIA_MANUSCRIPT_CLAIM_BINDINGS_V1","bindings":bindings},indent=2)+"\n")
supp=[r"\documentclass[10pt]{article}",r"\usepackage[margin=.65in]{geometry}",r"\usepackage{longtable,booktabs,hyperref}",r"\title{Supplement: Vithia 0-Vita-1 v0.1.0}",r"\author{Byron P. Lee\\Biobitworks}",r"\date{Release candidate --- DOI not yet reserved}",r"\begin{document}",r"\maketitle",r"\section{Governance}Canonical state is governed repository artifacts and receipts. Identity is not meaning; custody is not correctness; graph connectivity is not causality; simulation is not biological evidence.",r"\section{Complete claim matrix}",r"\small\begin{longtable}{p{.28\textwidth}p{.18\textwidth}p{.45\textwidth}}\toprule Claim & State & Evidence refs\\\midrule\endhead"]
for x in cm["entries"]: supp.append(x["claim_id"].replace("_",r"\_")+" & "+x["state"].replace("_",r"\_")+" & "+"; ".join(x["evidence_refs"]).replace("_",r"\_")+r"\\")
supp += [r"\bottomrule\end{longtable}\normalsize",r"\section{Secondary statistics}",f"E1 H1d Wilson 95\\% CI [{st['E1']['H1d']['wilson95'][0]:.6f},{st['E1']['H1d']['wilson95'][1]:.6f}]. E2 matched history delta {st['E2']['H2d']['mean_accuracy_difference_correct_minus_shuffled']:.6f}. E3 paired gain delta {st['E3']['H3b']['mean_paired_gain_difference']:.6f} bits and abstention fraction {st['E3']['abstention']['fraction']:.6f}.",r"\section{Reproduction}\begin{verbatim}python -m pytest -q\npython scripts/secret_scan.py\npython scripts/verify_breakpoints.py\npython scripts/verify_episode_mmr.py\npython scripts/secondary_stats.py\npython scripts/verify_publication_breakpoints.py\end{verbatim}",r"\section{External state}No DOI, Hugging Face commit, signature, or external publication is claimed until a successor receipt verifies it.",r"\end{document}"]
(S/"supplement.tex").write_text("\n".join(supp)+"\n")
print(json.dumps({"main_claim_bindings":len(bindings),"main_lines":len(main.splitlines()),"supp_lines":len(supp)},indent=2))
