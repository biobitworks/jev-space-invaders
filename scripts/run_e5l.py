#!/usr/bin/env python3
"""Governed LiquidAI E5L 1P successor. Every completed seed pair is checkpointed and pushed."""
from __future__ import annotations
import argparse,hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
import scripts.run_experiment as rx
from experiments import e5l_episodes as e5l
from experiments.common import write_jsonl,write_manifest
from scripts.liquid_runtime import verify as verify_runtime
from src.liquid_client import LiquidOllamaDecider
from src.s01.canon import git_head

EV=ROOT/"evidence/liquid"; OUT=ROOT/"results/vita01/e5l"; SEEDS=[1,2,3,4,5]
CODE=["src/liquid_client.py","scripts/liquid_runtime.py","experiments/e5l_episodes.py","scripts/run_e5l.py",
      "experiments/e5_episodes.py","experiments/e4b_ablation.py","experiments/e4a_snapshots.py",
      "src/perception.py","src/envcfg.py","src/s01/protocol.py"]
def runcheck(script):
    p=subprocess.run([sys.executable,script],cwd=ROOT,capture_output=True,text=True)
    if p.returncode: raise SystemExit(f"{script} failed:\n{p.stdout}\n{p.stderr}")
def seal(slug,state,atoms_paths,body,push,commit_paths):
    atoms=[rx.atom_record(str(p.relative_to(ROOT)) if isinstance(p,Path) else p,"E5LFCO","e5l") for p in atoms_paths]
    out=rx.create_breakpoint(slug,state,atoms,{"experiment_id":e5l.EXP,"pre_mmr_root":rx.pre_mmr(),**body})
    runcheck("scripts/verify_breakpoints.py"); runcheck("scripts/verify_episode_mmr.py"); runcheck("scripts/secret_scan.py")
    print(json.dumps({k:out[k] for k in ("bp_id","bp_root","mmr_size","mmr_root_after")},indent=2))
    if push:
        head=rx.publish(f"e5l: {slug} ({out['bp_id']})",["governance",*commit_paths])
        print("REMOTE_VERIFIED="+head)
    return out
def manifest():
    p=EV/"RUNTIME_MANIFEST.json"
    if not p.exists(): raise SystemExit("Liquid runtime manifest missing")
    m=json.loads(p.read_text())
    if m.get("LIQUID_LOADED")!="YES": raise SystemExit("LIQUID_LOADED != YES")
    return m
def decider():
    m=manifest()
    return LiquidOllamaDecider(m["endpoint"],m["served_model"],timeout_s=60,max_retries=2)
def frozen():
    found=None
    for f in sorted(rx.BP_DIR.glob("*.json")):
        d=json.loads(f.read_text())
        if d.get("stage")=="E5L_PREREG": found=d
    if found is None: raise SystemExit("E5L prereg missing")
    for a in found["atoms"]:
        p=ROOT/a["path"]
        if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest()!=a["sha256"]:
            raise SystemExit(f"frozen atom changed: {a['path']}")
    return found
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("stage",choices=["runtime","probe","prereg","run-1p"])
    ap.add_argument("--push",action="store_true")
    ap.add_argument("--branch",default="vithia-space")
    ap.add_argument("--max-decisions",type=int,default=100)
    a=ap.parse_args(); rx.BRANCH=a.branch
    if a.push: rx.preflight()
    EV.mkdir(parents=True,exist_ok=True); OUT.mkdir(parents=True,exist_ok=True)
    if a.stage=="runtime":
        m=verify_runtime()
        seal("e5l-liquid-runtime","LIQUID_RUNTIME_VERIFIED",
             [EV/"RUNTIME_MANIFEST.json","src/liquid_client.py","scripts/liquid_runtime.py"],
             {"stage":"E5L_RUNTIME","provider":"liquid","served_model":m["served_model"],
              "weight_sha256":m["weight_sha256"],"probabilities":"NOT_AVAILABLE"},
             a.push,["evidence/liquid"])
        return
    if a.stage=="probe":
        manifest(); pr=e5l.latency_probe(decider(),20)
        (EV/"E5L_LATENCY_PROBE.json").write_text(json.dumps(pr,indent=2)+"\n")
        if pr["valid_action_rate"]!=1.0 or pr["fallback_rate"]!=0.0:
            raise SystemExit(f"Liquid probe failed output contract: {pr}")
        seal("e5l-liquid-probe","SETUP_SMOKE_NON_EXPERIMENTAL",
             [EV/"E5L_LATENCY_PROBE.json",EV/"RUNTIME_MANIFEST.json"],
             {"stage":"E5L_PROBE","probe":pr},a.push,["evidence/liquid"])
        return
    if a.stage=="prereg":
        if a.max_decisions<=0: raise SystemExit("max-decisions must be positive")
        pr=json.loads((EV/"E5L_LATENCY_PROBE.json").read_text()); m=manifest()
        cfg={"provider":"liquid","served_model":m["served_model"],"weight_sha256":m["weight_sha256"],
             "arms":e5l.ARMS,"seeds":SEEDS,"order":"interleave LQ_RAW then LV_VITA01 by seed",
             "max_decisions":a.max_decisions,"cap_kind":"prospectively frozen development cap",
             "probe_p50_ms":pr["p50_ms"],"probe_p95_ms":pr["p95_ms"],
             "primary":"paired episode score LV_VITA01 - LQ_RAW",
             "statistics":"Wilcoxon two-sided n=5; min p=.0625; SUPPORTED at alpha=.05 impossible; deterministic bootstrap CI",
             "delta_g_star":"NOT_COMPUTED","e4c":"BLOCKED_OR_UNDERPOWERED BP-0026",
             "probabilities":"NOT_AVAILABLE","confidence":"NOT_AVAILABLE"}
        (EV/"E5L_PREREG_CONFIG.json").write_text(json.dumps(cfg,indent=2)+"\n")
        atoms=["docs/prereg/E5L_LIQUID_1P.md",EV/"E5L_PREREG_CONFIG.json",EV/"RUNTIME_MANIFEST.json",
               EV/"E5L_LATENCY_PROBE.json",*CODE]
        seal("e5l-prereg","PREREG_SEALED",atoms,{"stage":"E5L_PREREG","config":cfg},a.push,["evidence/liquid"])
        return
    fz=frozen(); cfg=json.loads((EV/"E5L_PREREG_CONFIG.json").read_text()); d=decider()
    for seed in SEEDS:
        seed_json=OUT/f"E5L_1P_SEED{seed}.json"
        if seed_json.exists(): continue
        if a.push: rx.preflight()
        runs=[]; trace_files=[]
        for arm in ("LQ_RAW","LV_VITA01"):
            run,trace=e5l.run_episode(arm,d,seed,cfg["max_decisions"])
            tp=OUT/f"1p_{arm}_seed{seed}.jsonl.gz"; run["trace_sha256"]=e5l.write_trace(tp,trace)
            runs.append(run); trace_files.append(tp)
            print(json.dumps({k:run[k] for k in ("arm","seed","score","decisions","truncated","latency_ms_p50")}))
        seed_json.write_text(json.dumps({"prereg_breakpoint":fz["breakpoint_id"],"seed":seed,"runs":runs},indent=2)+"\n")
        seal(f"e5l-1p-seed{seed}","PARTIAL_PROGRESS_SEED_PAIR_SEALED",[seed_json,*trace_files],
             {"stage":"E5L_1P_PROGRESS","prereg":fz["breakpoint_id"],"seed":seed,"completed_pair":True},
             a.push,["results/vita01/e5l"])
    runs=[]
    for seed in SEEDS: runs.extend(json.loads((OUT/f"E5L_1P_SEED{seed}.json").read_text())["runs"])
    analysis=e5l.analyze(runs)
    dset=ROOT/"data/s01"/e5l.OUT_ID; dset.mkdir(parents=True,exist_ok=True)
    rows_sha,_,nrows=write_jsonl(dset/"rows.jsonl",runs)
    mf=write_manifest(dset,dataset_id=e5l.OUT_ID,schema="episode-level LiquidAI raw vs Vita01-context rows",
        kind="output",source="E5L_LIQUID_1P",generation_code=CODE,
        config={"arms":e5l.ARMS,"max_decisions":cfg["max_decisions"],"analysis":analysis},
        seeds={"episodes":SEEDS},parent_evidence=[fz["breakpoint_id"],"evidence/liquid/RUNTIME_MANIFEST.json"],
        claim_ceiling="development comparator only; NON_TYPESAFE_JEV; NON_OPENJEV; n=5 descriptive/fail-to-reject only")
    receipt={"schema":"E5L_EXPERIMENT_RECEIPT_V1","experiment_id":e5l.EXP,"prereg_breakpoint":fz["breakpoint_id"],
             "provider":"liquid","served_model":manifest()["served_model"],"input_contracts":e5l.ARMS,
             "output_dataset":{"dataset_id":e5l.OUT_ID,"fmo_root":mf["fmo_root"],"rows_sha256":rows_sha,"rows":nrows},
             "analysis":analysis,"terminal_state":analysis["claim_state"],"code_commit":git_head(),
             "not_tested":["TypeSafe JEV","OpenJev","governed DeltaG*","2P Liquid successor"],
             "e4c_quality":"BLOCKED_OR_UNDERPOWERED; not cited as action-quality evidence","signature_state":"NOT_SIGNED"}
    rp=EV/"E5L_1P_EXPERIMENT_RECEIPT.json"; rp.write_text(json.dumps(receipt,indent=2)+"\n")
    atoms=[rx.atom_record(str(p.relative_to(ROOT)),"DatasetFileFCO" if p.name!="MANIFEST.json" else "DatasetManifestFCO","output_dataset")
           for p in sorted(dset.iterdir()) if p.is_file()]
    atoms.append(rx.atom_record(str(rp.relative_to(ROOT)),"ExperimentReceiptFCO","receipt"))
    out=rx.create_breakpoint("e5l-1p-result","RESULT_"+analysis["claim_state"],atoms,
         {"experiment_id":e5l.EXP,"stage":"E5L_1P_RESULT","prereg":fz["breakpoint_id"],
          "pre_mmr_root":rx.pre_mmr(),"terminal_state":analysis["claim_state"],"analysis":analysis})
    runcheck("scripts/verify_breakpoints.py"); runcheck("scripts/verify_episode_mmr.py"); runcheck("scripts/secret_scan.py")
    print(json.dumps({"analysis":analysis,**{k:out[k] for k in ("bp_id","bp_root","mmr_size","mmr_root_after")}},indent=2))
    if a.push:
        head=rx.publish(f"e5l: 1p result {analysis['claim_state']} ({out['bp_id']})",
                        ["data/s01","evidence/liquid","governance"])
        print("REMOTE_VERIFIED="+head)
if __name__=="__main__": main()

