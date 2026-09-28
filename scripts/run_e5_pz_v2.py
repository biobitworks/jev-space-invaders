#!/usr/bin/env python3
"""E5 v2 supplement.

Use scripts/run_e5.py for probe, 1P and ROM gate.
Use this script for the E5 prereg and 2P execution so the PZ-aware OpenJev client
is explicitly frozen as a code atom before any 2P scientific call.
"""
from __future__ import annotations
import argparse, json, math, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import scripts.run_e5 as base
from experiments import e5_2p, e5_episodes
from src.openjev_client_pz import PZOpenJevDecider, PZ_ACTIONS

EV=ROOT/"evidence"/"e5"
OUT=ROOT/"results"/"vita01"/"e5"
SEEDS=[1,2,3,4,5]
CODE_V2=sorted(set(base.CODE+[
    "src/openjev_client_pz.py","scripts/run_e5_pz_v2.py","docs/prereg/E5_PZ_CLIENT_V2.md"
]))

def pz_decider():
    man=json.loads((ROOT/"evidence/openjev/RUNTIME_MANIFEST.json").read_text())
    if man.get("OPENJEV_LOADED")!="YES":
        raise SystemExit("OPENJEV_LOADED != YES")
    return PZOpenJevDecider(man["endpoint"].rsplit("/v1/systemone",1)[0],
                            "openjev",max_retries=2,timeout_s=120)

def prereg(budget_hours:float,push:bool):
    pr=json.loads((EV/"LATENCY_PROBE.json").read_text())
    max_dec=max(50,math.floor(budget_hours*3600*1000/(pr["p95_ms"]*1.15)/50))
    cfg={"schema":"E5_PREREG_CONFIG_V2","arms":e5_episodes.ARMS,"seeds":SEEDS,
         "order":"interleave OJ,VS by seed; 2P M1,M2,M2prime,M3 by seed",
         "max_decisions":max_dec,"budget_hours":budget_hours,"probe_p95_ms":pr["p95_ms"],
         "ontology_ids":e5_2p.ONTOLOGY_IDS,
         "question_1p":"src/deciders.MOVE_QUESTION","question_2p":e5_2p.QUESTION_2P,
         "pz_client":"src/openjev_client_pz.py:PZOpenJevDecider",
         "tests":{"1p":"Wilcoxon signed-rank VS vs OJ score, n=5; min two-sided p=0.0625; SUPPORTED impossible at alpha=0.05",
                  "2p":"M2 and M2prime paired by seed and seat; small-n descriptive/effect-size reporting"},
         "labels":["provider=openjev","NON_TYPESAFE_JEV","NON_COUNTED_FOR_TYPESAFE_PERFORMANCE"],
         "delta_g_star":"NOT_COMPUTED"}
    (EV/"E5_PREREG_CONFIG.json").write_text(json.dumps(cfg,indent=2)+"\n")
    base.seal("e5-prereg-v2","PREREG_SEALED",
        ["docs/prereg/E5_LADDER.md","docs/prereg/E5_PZ_CLIENT_V2.md",
         EV/"E5_PREREG_CONFIG.json","evidence/openjev/RUNTIME_MANIFEST.json",*CODE_V2],
        {"stage":"E5_PREREG","protocol_version":"V2_PZ_ACTION_SAFE"},
        push,["evidence/e5"])

def run_2p(rom_dir:str|None,push:bool):
    fz=base.frozen()
    gate=e5_2p.rom_gate(rom_dir)
    if gate["state"]!="ROM_PRESENT":
        raise SystemExit(f"2P blocked: {gate["reason"]}")
    if tuple(e5_2p.ONTOLOGY_PZ)!=tuple(PZ_ACTIONS):
        raise SystemExit("PZ client/action ontology mismatch")
    from pettingzoo.atari import space_invaders_v2
    from src.perception import Perception
    cfg=json.loads((EV/"E5_PREREG_CONFIG.json").read_text())
    matchups={"M1":("VS","VS"),"M2":("VS","OJ"),"M2prime":("OJ","VS"),"M3":("OJ","OJ")}
    for name,(s0,s1) in matchups.items():
        summaries=[]; files=[]
        for seed in SEEDS:
            d0,d1=pz_decider(),pz_decider()
            summ,rows=e5_2p.run_match(
                lambda:space_invaders_v2.parallel_env(auto_rom_install_path=rom_dir),
                Perception,{"first_0":d0,"second_0":d1},
                {"first_0":s0,"second_0":s1},seed,cfg["max_decisions"])
            tp=OUT/f"2p_v2_{name}_seed{seed}.jsonl.gz"
            summ["trace_sha256"]=e5_episodes.write_trace(tp,rows)
            summaries.append(summ); files.append(tp)
        sp=OUT/f"E5_2P_V2_{name}.json"
        sp.write_text(json.dumps({"matchup":name,"seats":[s0,s1],"rom":gate,
                                  "prereg_breakpoint":fz["breakpoint_id"],"runs":summaries},indent=2)+"\n")
        base.seal(f"e5-2p-v2-{name.lower()}","EXECUTED_RESULT_ANALYSIS_PENDING",
                  [sp,*files],{"stage":"E5_2P","matchup":name,"prereg":fz["breakpoint_id"],
                  "pz_client":"PZOpenJevDecider"},push,["results/vita01/e5"])

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("stage",choices=["prereg","run-2p"])
    ap.add_argument("--push",action="store_true")
    ap.add_argument("--branch",default="vithia-space")
    ap.add_argument("--budget-hours",type=float)
    ap.add_argument("--rom-dir")
    a=ap.parse_args()
    base.rx.BRANCH=a.branch
    if a.push: base.rx.preflight()
    EV.mkdir(parents=True,exist_ok=True); OUT.mkdir(parents=True,exist_ok=True)
    if a.stage=="prereg":
        if a.budget_hours is None or a.budget_hours<=0:
            raise SystemExit("explicit --budget-hours is required before E5 freeze")
        prereg(a.budget_hours,a.push)
    else:
        run_2p(a.rom_dir,a.push)

if __name__=="__main__":
    main()

