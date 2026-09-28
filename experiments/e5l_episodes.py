"""E5L 1P: LiquidAI System-1 under A0_RAW vs A5_VITA01_FULL."""
from __future__ import annotations
import gzip,hashlib,json,time
from pathlib import Path
import numpy as np
from experiments.e5_episodes import context as e5_context
from experiments.common import write_jsonl,write_manifest
from src.actions import ACTIONS
from src.envcfg import make_env
from src.fmo import hp,mmr_root
from src.perception import Perception
from src.s01.canon import content_id

EXP="E5L_LIQUID_VS_VITA01_1P"
OUT_ID="S01_E5L_1P_LIQUID_RESULTS_V1"
ARMS={"LQ_RAW":"A0_RAW","LV_VITA01":"A5_VITA01_FULL"}
LABELS=["provider=liquid","NON_TYPESAFE_JEV","NON_OPENJEV","NON_COUNTED_FOR_TYPESAFE_PERFORMANCE"]
HIST=3

def _ctx(arm,state,hist):
    return e5_context("OJ" if arm=="LQ_RAW" else "VS",state,hist[-HIST:])

def run_episode(arm,decider,seed,max_decisions):
    env,per=make_env(),Perception(); obs,info=env.reset(seed=seed)
    lives0=int(info["lives"]); score=0.0; prev="NOOP"; hist=[]; trace=[]; term=trunc=capped=False
    tstart=time.perf_counter()
    for t in range(max_decisions):
        t0=time.perf_counter()
        state=per.observe(obs,lives=int(info["lives"]),score=score,step=t,prev_action=prev)
        ctx=_ctx(arm,state,hist); s0_ms=(time.perf_counter()-t0)*1000
        t0=time.perf_counter(); body=decider.request_body(ctx); ser_ms=(time.perf_counter()-t0)*1000
        t0=time.perf_counter(); d=decider.decide_body(body,prev); dec_ms=(time.perf_counter()-t0)*1000
        obs,r,term,trunc,info=env.step(ACTIONS.index(d.action)); score+=float(r)
        rec={"t":t,"arm":arm,"context_arm":ARMS[arm],"state_id":content_id(state),"context_id":content_id(ctx),
             "request_sha256":hashlib.sha256(body).hexdigest(),"action":d.action,"proposed":d.proposed_action,
             "p":"NOT_AVAILABLE","conf":"NOT_AVAILABLE","served_model":d.served_model,"fallback":d.fallback_reason,
             "reward":float(r),"lives":int(info["lives"]),"next_frame_sha256":hashlib.sha256(obs.tobytes()).hexdigest(),
             "labels":LABELS}
        rec["leaf"]=hp("EPISODE_LEAF_V1",t,content_id(rec)).hex()
        rec["ms"]={"s0":round(s0_ms,3),"serialize":round(ser_ms,3),"decider":round(dec_ms,2)}
        trace.append(rec); hist.append(state); prev=d.action
        if term or trunc: break
    else: capped=True
    env.close(); root,_=mmr_root([bytes.fromhex(x["leaf"]) for x in trace])
    dec=np.array([x["ms"]["decider"] for x in trace]); tot=np.array([sum(x["ms"].values()) for x in trace])
    run={"experiment_id":EXP,"arm":arm,"context_arm":ARMS[arm],"seed":seed,"score":score,"decisions":len(trace),
         "frames":int(info["episode_frame_number"]),"lives_lost":lives0-int(info["lives"]),
         "terminated":bool(term),"truncated":bool(trunc or capped),"max_decisions":max_decisions,
         "fallback_rate":round(sum(bool(x["fallback"]) for x in trace)/len(trace),4),
         "valid_action_rate":round(sum(x["proposed"] in ACTIONS for x in trace)/len(trace),4),
         "latency_ms_p50":round(float(np.percentile(dec,50)),2),"latency_ms_p95":round(float(np.percentile(dec,95)),2),
         "total_ms_p50":round(float(np.percentile(tot,50)),2),"total_ms_mean":round(float(np.mean(tot)),2),
         "wall_clock_s":round(time.perf_counter()-tstart,1),
         "served_model":",".join(sorted({x["served_model"] for x in trace if x["served_model"]})) or None,
         "provider":"liquid","labels":LABELS,"probability_entropy":"NOT_AVAILABLE",
         "episode_mmr_root":root,"episode_mmr_size":len(trace)}
    return run,trace

def write_trace(path,trace):
    raw="".join(json.dumps(x,separators=(",",":"))+"\n" for x in trace).encode()
    path.write_bytes(gzip.compress(raw,mtime=0))
    return hashlib.sha256(path.read_bytes()).hexdigest()

def latency_probe(decider,n=20):
    ms=[]; valid=0; fallback=0; choices=[]
    for i in range(n):
        body=decider.request_body({"state":{"label":"SETUP_SMOKE","note":"NON_EXPERIMENTAL","i":i}})
        t=time.perf_counter(); d=decider.decide_body(body,"NOOP"); ms.append((time.perf_counter()-t)*1000)
        valid+=int(d.proposed_action in ACTIONS); fallback+=int(d.fallback); choices.append(d.proposed_action)
    a=np.array(ms)
    return {"n":n,"p50_ms":round(float(np.percentile(a,50)),2),"p95_ms":round(float(np.percentile(a,95)),2),
            "valid_action_rate":valid/n,"fallback_rate":fallback/n,"choices":choices,
            "label":"SETUP_SMOKE NON_EXPERIMENTAL","probabilities":"NOT_AVAILABLE"}

def analyze(runs):
    from scipy.stats import wilcoxon
    by={(r["seed"],r["arm"]):r for r in runs}; diffs=[]
    for seed in range(1,6):
        diffs.append(float(by[(seed,"LV_VITA01")]["score"])-float(by[(seed,"LQ_RAW")]["score"]))
    p=1.0 if not any(diffs) else float(wilcoxon(diffs,alternative="two-sided",zero_method="wilcox").pvalue)
    rng=np.random.default_rng(20260928); arr=np.array(diffs); boots=np.array([rng.choice(arr,len(arr),replace=True).mean() for _ in range(10000)])
    ci=[round(float(np.percentile(boots,2.5)),3),round(float(np.percentile(boots,97.5)),3)]
    net=[]
    for seed in range(1,6):
        net.append(by[(seed,"LQ_RAW")]["total_ms_mean"]-by[(seed,"LV_VITA01")]["total_ms_mean"])
    return {"paired_score_differences_lv_minus_lq":diffs,"mean_score_difference":round(float(np.mean(diffs)),3),
            "median_score_difference":round(float(np.median(diffs)),3),"bootstrap_95ci_mean":ci,
            "wilcoxon_two_sided_p":p,"minimum_attainable_two_sided_p_n5":0.0625,
            "claim_state":"FAIL_TO_REJECT_H0" if p>=0.05 else "DESCRIPTIVE_ONLY_NO_SUPPORTED_ALLOWED",
            "net_time_saved_ms_lq_minus_lv_per_seed":net,
            "quality_source":"episode score only; E4C remains BLOCKED_OR_UNDERPOWERED; no E4C action-quality claim"}

