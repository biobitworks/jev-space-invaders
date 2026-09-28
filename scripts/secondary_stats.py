#!/usr/bin/env python3
from __future__ import annotations
import csv, json, math
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"evidence"/"statistical_successor"
OUT.mkdir(parents=True,exist_ok=True)
SEED=20260927
B=10000

def rows(p):
    return [json.loads(x) for x in Path(p).read_text().splitlines() if x.strip()]

def pct_ci(vals, stat=np.mean, seed=SEED):
    a=np.asarray(vals,float)
    if len(a)==0: return [None,None]
    rng=np.random.default_rng(seed)
    idx=rng.integers(0,len(a),size=(B,len(a)))
    bs=np.apply_along_axis(stat,1,a[idx])
    q=np.quantile(bs,[.025,.975])
    return [float(q[0]),float(q[1])]

def wilson(k,n,z=1.959963984540054):
    p=k/n
    d=1+z*z/n
    c=(p+z*z/(2*n))/d
    h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [c-h,c+h]

def cliffs(a,b):
    a=np.asarray(a); b=np.asarray(b)
    gt=sum(int(x>y) for x in a for y in b)
    lt=sum(int(x<y) for x in a for y in b)
    return (gt-lt)/(len(a)*len(b))

e1=rows(ROOT/"data/s01/S01_ECA_256_RESULTS_V1/rows.jsonl")
def sel(kind,ics): return [o for o in e1 if o["kind"]==kind and o["ic"] in ics]
def tfinal(o):
    m=o["series"]["map"]
    return next(i for i,v in enumerate(m,1) if v==m[-1])
rnd=["rand1","rand2","rand3"]
bf=sel("bit_flip",rnd)
h1d_k=sum(o["series"]["rank"][-1]==1 for o in bf); h1d_n=len(bf); h1d_p=h1d_k/h1d_n
t_mr=[tfinal(o) for o in sel("missing_row",rnd)]
t_ex=[tfinal(o) for o in sel("exact",rnd)]
s_mr=[tfinal(o) for o in sel("missing_row",["single"])]
s_ex=[tfinal(o) for o in sel("exact",["single"])]

def med_boot_diff(a,b,seed):
    a=np.asarray(a); b=np.asarray(b); rng=np.random.default_rng(seed)
    vals=[]
    for _ in range(B):
        aa=a[rng.integers(0,len(a),len(a))]
        bb=b[rng.integers(0,len(b),len(b))]
        vals.append(float(np.median(aa)-np.median(bb)))
    return [float(x) for x in np.quantile(vals,[.025,.975])]

hist=rows(ROOT/"data/s01/S01_LIFE_CONTEXT_RESULTS_V1/history_controls.jsonl")
hm={}
for r in hist: hm.setdefault((r["scene"],r["t"]),{})[r["condition"]]=r
accdiff=[]; unkdiff=[]
for key,g in hm.items():
    if {"CORRECT_HISTORY","SHUFFLED_HISTORY","NO_HISTORY"}<=set(g):
        c,s,n=g["CORRECT_HISTORY"],g["SHUFFLED_HISTORY"],g["NO_HISTORY"]
        if c["labelled"] and s["labelled"]:
            accdiff.append(c["correct"]/c["labelled"]-s["correct"]/s["labelled"])
        if n["labelled"] and c["labelled"]:
            unkdiff.append(n["unknown"]/n["labelled"]-c["unknown"]/c["labelled"])

e3=rows(ROOT/"data/s01/S01_MINESWEEPER_RESULTS_V1/rows.jsonl")
q=[r["question"] for r in e3 if r.get("question")]
d3=np.array([x["actual_gain_bits"]-x["random_actual_gain_bits"] for x in q],float)
g3=np.array([x["actual_gain_bits"]-x["eig_bits"] for x in q],float)
dz=float(d3.mean()/d3.std(ddof=1)) if len(d3)>1 and d3.std(ddof=1)>0 else None
ab=sum(r["kernel_status"]=="ABSTAIN_SIZE_LIMIT" for r in e3)

res={
 "schema":"VITA01_POST_CONFIRMATORY_STATISTICAL_ANALYSIS_V1",
 "mode":"POST_CONFIRMATORY_SECONDARY",
 "claim_mutation":False,
 "bootstrap":{"seed":SEED,"resamples":B,"interval":"percentile_95"},
 "E1":{
  "H1d":{"successes":h1d_k,"n":h1d_n,"fraction":h1d_p,"wilson95":wilson(h1d_k,h1d_n),
         "difference_from_preregistered_0_90":h1d_p-0.90,"original_state":"NOT_SUPPORTED"},
  "H1e":{"n_missing":len(t_mr),"n_exact":len(t_ex),"cliffs_delta":cliffs(t_mr,t_ex),
         "median_difference":float(np.median(t_mr)-np.median(t_ex)),
         "median_difference_bootstrap95":med_boot_diff(t_mr,t_ex,SEED+1),
         "original_state":"FAIL_TO_REJECT_H0"},
  "H1e_v2":{"n_missing":len(s_mr),"n_exact":len(s_ex),"cliffs_delta":cliffs(s_mr,s_ex),
         "median_difference":float(np.median(s_mr)-np.median(s_ex)),
         "median_difference_bootstrap95":med_boot_diff(s_mr,s_ex,SEED+2),
         "original_state":"FAIL_TO_REJECT_H0"}
 },
 "E2":{"H2d":{
   "matched_units":len(accdiff),
   "mean_accuracy_difference_correct_minus_shuffled":float(np.mean(accdiff)),
   "bootstrap95_accuracy_difference":pct_ci(accdiff,seed=SEED+3),
   "mean_unknown_difference_no_history_minus_correct":float(np.mean(unkdiff)),
   "bootstrap95_unknown_difference":pct_ci(unkdiff,seed=SEED+4),
   "original_state":"SUPPORTED"
 }},
 "E3":{
   "H3b":{"pairs":len(d3),"mean_paired_gain_difference":float(d3.mean()),"median_paired_gain_difference":float(np.median(d3)),
          "paired_cohen_dz":dz,"bootstrap95_mean_difference":pct_ci(d3,seed=SEED+5),"original_state":"SUPPORTED"},
   "H3c":{"pairs":len(g3),"mean_signed_actual_minus_eig":float(g3.mean()),
          "abs_mean_gap":float(abs(g3.mean())),
          "bootstrap95_signed_mean":pct_ci(g3,seed=SEED+6),
          "bootstrap95_abs_mean_gap":[abs(x) for x in pct_ci(g3,seed=SEED+7)],
          "original_state":"SUPPORTED"},
   "abstention":{"states":ab,"total_states":len(e3),"fraction":ab/len(e3)}
 }
}
(OUT/"STATISTICAL_ANALYSIS.json").write_text(json.dumps(res,indent=2)+"\n")
flat=[]
def add(exp,claim,metric,val):
    if isinstance(val,(list,dict)): val=json.dumps(val,sort_keys=True)
    flat.append([exp,claim,metric,val])
for exp in ["E1","E2","E3"]:
    for claim,body in res[exp].items():
        if isinstance(body,dict):
            for k,v in body.items(): add(exp,claim,k,v)
with (OUT/"STATISTICAL_ANALYSIS.csv").open("w",newline="") as f:
    w=csv.writer(f); w.writerow(["experiment","claim","metric","value"]); w.writerows(flat)
print(json.dumps(res,indent=2))
