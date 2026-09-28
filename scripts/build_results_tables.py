#!/usr/bin/env python3
from __future__ import annotations
import csv,json
from pathlib import Path
R=Path(__file__).resolve().parents[1]
P=R/"publication"; D=P/"data"; T=P/"tables"
D.mkdir(parents=True,exist_ok=True); T.mkdir(parents=True,exist_ok=True)

def j(p):
    return json.loads((R/p).read_text())

receipts={x:j(f"evidence/s01/{x}/EXPERIMENT_RECEIPT.json") for x in ["E0_ADDRESSABILITY","E1_ECA","E2_LIFE","E3_MINESWEEPER"]}
stats=j("evidence/statistical_successor/STATISTICAL_ANALYSIS.json")
ledger=j("governance/MMR_LEDGER.json")

summary=[
 ["E0","Exact addressability",receipts["E0_ADDRESSABILITY"]["terminal_state"],receipts["E0_ADDRESSABILITY"]["replay"]["replay_level"]],
 ["E1","Elementary cellular automata",receipts["E1_ECA"]["terminal_state"],receipts["E1_ECA"]["replay"]["replay_level"]],
 ["E2","Context/history in Life",receipts["E2_LIFE"]["terminal_state"],receipts["E2_LIFE"]["replay"]["replay_level"]],
 ["E3","Hidden-world uncertainty",receipts["E3_MINESWEEPER"]["terminal_state"],receipts["E3_MINESWEEPER"]["replay"]["replay_level"]],
 ["E4A","Space Invaders snapshot freeze","INPUT_FROZEN_NO_DECIDER_CALLS","REPLAY_VERIFIED_INPUT"]
]
with (D/"experiment_summary.csv").open("w",newline="") as f:
    w=csv.writer(f); w.writerow(["experiment","purpose","state","replay"]); w.writerows(summary)

claims=[]
for exp,r in receipts.items():
    for c in r["claims"]:
        claims.append([exp,c["id"],c["state"]])
with (D/"claim_outcomes.csv").open("w",newline="") as f:
    w=csv.writer(f); w.writerow(["experiment","claim","state"]); w.writerows(claims)

bps=[[e["seq"],e["bp_id"],e["bp_root"],e["mmr_root_after"]] for e in ledger["entries"]]
with (D/"scientific_breakpoints.csv").open("w",newline="") as f:
    w=csv.writer(f); w.writerow(["seq","breakpoint","root","mmr_root_after"]); w.writerows(bps)

model_state=[
 ["JEV hosted","NOT_TESTED","No hosted JEV counted run in v0.1.0"],
 ["OpenJEV local stand-in","NOT_TESTED","Prospective E4B successor"],
 ["System One adapter baseline","NOT_TESTED","Prospective E4B/E4C successor"],
 ["Liquid AI","NOT_TESTED","Prospective portability successor"],
 ["Ollama/Ollarma","NOT_TESTED","Prospective portability successor"],
 ["Vithia-S0","IMPLEMENTED","Deterministic context compiler; no learned weights in this release"]
]
with (D/"model_state.csv").open("w",newline="") as f:
    w=csv.writer(f); w.writerow(["model_or_lane","state","note"]); w.writerows(model_state)

limitations=[
 ["E1","H1d","NOT_SUPPORTED","rank-1 fraction 0.806 below 0.90 preregistered threshold"],
 ["E1","H1e","FAIL_TO_REJECT_H0","metric non-discriminating; medians both 1"],
 ["E1","H1e_v2","FAIL_TO_REJECT_H0","prospective successor also did not reject H0"],
 ["E3","Replay","REPLAY_LEVEL_2","frozen inputs match but output rows differ from rehearsal runtime"],
 ["E3","Size limit","ABSTAIN_SIZE_LIMIT","66 states / 6484 cells excluded by preregistered abstention rule"],
 ["E4A","Downstream model","NOT_TESTED","frozen input only; no decider calls"],
 ["Framework","DeltaGStar","NOT_COMPUTED","private successor component not computed here"],
 ["Replication","Cross-host","DEFERRED_NOT_FAILED","magicPRObox unavailable during this build"],
 ["Evidence","Biological transfer","NOT_TESTED","all current evidence is simulated"],
 ["Integrity","Signature","NOT_SIGNED","no verified cryptographic signing"]
]
with (D/"limitations.csv").open("w",newline="") as f:
    w=csv.writer(f); w.writerow(["scope","item","state","note"]); w.writerows(limitations)

plot={
 "E1":{"h1d_fraction":stats["E1"]["H1d"]["fraction"],"h1d_ci":stats["E1"]["H1d"]["wilson95"],"threshold":0.90,
       "h1e_delta":stats["E1"]["H1e"]["cliffs_delta"],"h1e_v2_delta":stats["E1"]["H1e_v2"]["cliffs_delta"]},
 "E2":stats["E2"]["H2d"],
 "E3":stats["E3"]
}
(D/"plot_data.json").write_text(json.dumps(plot,indent=2)+"\n")

def esc(s):
    return str(s).replace("\\","\\textbackslash{}").replace("_","\\_").replace("%","\\%").replace("&","\\&")

def tex_table(path,headers,rows,caption,label):
    cols="l"*len(headers)
    out=["\\begin{table}[t]","\\centering","\\small",f"\\begin{{tabular}}{{{cols}}}","\\toprule",
         " & ".join(esc(x) for x in headers)+" \\\\","\\midrule"]
    out += [" & ".join(esc(x) for x in r)+" \\\\" for r in rows]
    out += ["\\bottomrule","\\end{tabular}",f"\\caption{{{caption}}}",f"\\label{{{label}}}","\\end{table}"]
    path.write_text("\n".join(out)+"\n")

tex_table(T/"T2_experiments.tex",["Exp.","Purpose","State","Replay"],summary,
          "Experiment ladder and terminal states. Scientific states are not integrity PASS/FAIL labels.","tab:experiments")
tex_table(T/"T3_claims.tex",["Experiment","Claim","State"],claims,
          "Confirmatory claim outcomes. Negative and null outcomes are retained.","tab:claims")
tex_table(T/"T6_models.tex",["Lane","State","Note"],model_state,
          "Downstream model and adapter state in v0.1.0.","tab:models")
tex_table(T/"T7_limitations.tex",["Scope","Item","State","Note"],limitations,
          "Preserved limitations, abstentions, and unresolved states.","tab:limitations")

replay=[[r[0],r[3]] for r in summary]
tex_table(T/"T4_replay.tex",["Experiment","Replay state"],replay,
          "Replay and freeze state by experiment.","tab:replay")

last=bps[-16:]
tex_table(T/"T5_breakpoints.tex",["Seq","Breakpoint","Root","MMR root after"],
          [[a,b,c[:12]+"...",d[:12]+"..."] for a,b,c,d in last],
          "Scientific breakpoint/MMR lineage (truncated display digests; full digests are machine-readable).","tab:breakpoints")

terms=[
 ["FCO","Independently addressable governed object/atom"],
 ["FCG","Typed declared relationships among FCOs; not causality by connectivity"],
 ["VitaState","Finite persistent context state with predecessor lineage"],
 ["VitaContext","Persistent, versioned contextual substrate"],
 ["ContextPacket","Bounded projection used for one downstream question/decision"],
 ["0-Vita-1","Public S0-S1 adapter protocol (VITA01)"],
 ["Exact identity","Exact canonical bytes/content identity"],
 ["Contextual equivalence","Same class under one frozen equivalence rule"],
 ["Statistical similarity","Quantitative relation; does not alter exact identity"]
]
tex_table(T/"T1_terminology.tex",["Term","Meaning"],terms,
          "Core terminology and type distinctions.","tab:terms")

print(json.dumps({"summary_rows":len(summary),"claims":len(claims),"breakpoints":len(bps),"limitations":len(limitations)},indent=2))
