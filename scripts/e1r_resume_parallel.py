#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, os, time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np
import scripts.e1r_daisy_execute as e
from src.fmo import fmo_root, leaf, mmr_leaf, mmr_root, sha256_file

ROOT=e.ROOT
BRANCH=e.BRANCH
EXPECTED_LATEST="UFA-JEV-BP-0033"

def screen_one(rule:int):
    h=[];v=[];t=[]
    for stratum in e.STRATA:
        for sev in e.SEVERITIES:
            rr,tt=e.horizontal_batch(rule,stratum,e.PILOT_REPS,sev,True)
            h.extend(rr);t.extend(tt)
            for op in e.VERT_OPS:
                v.extend(e.vertical_batch(rule,stratum,e.PILOT_REPS,sev,op))
    return rule,h,v,t

def exact_digest(obj):
    return hashlib.sha256(e.cbytes(obj)).hexdigest()

def verify_current_parent():
    led=json.loads((ROOT/"governance/MMR_LEDGER.json").read_text())
    if led["entries"][-1]["bp_id"]!=EXPECTED_LATEST:
        raise RuntimeError("resume requires latest breakpoint "+EXPECTED_LATEST)
    return led["entries"][-1]

def final_verify(min_new=34):
    led=json.loads((ROOT/"governance/MMR_LEDGER.json").read_text())
    leaves=[]
    for i,x in enumerate(led["entries"]):
        p=ROOT/x["bp_file"];fsha,_=sha256_file(p)
        if fsha!=x["bp_file_sha256"]:raise RuntimeError("bp file mismatch "+x["bp_id"])
        if x["root_kind"]=="FMO_V1_BREAKPOINT_ATOMS" and int(x["bp_id"].split("-")[-1])>=min_new:
            d=json.loads(p.read_text());groups=defaultdict(list)
            for a in d["atoms"]:
                q=ROOT/a["path"]
                if not q.exists():raise RuntimeError("missing new atom "+a["path"])
                sha,n=sha256_file(q)
                if sha!=a["sha256"] or n!=a["bytes"]:raise RuntimeError("changed new atom "+a["path"])
                lf=leaf(a["path"],a["bytes"],a["sha256"])
                if lf.hex()!=a["fmo_leaf"]:raise RuntimeError("leaf mismatch "+a["path"])
                groups[a["group"]].append((a["path"],lf))
            root,_=fmo_root(dict(groups))
            if root!=x["bp_root"]:raise RuntimeError("root mismatch "+x["bp_id"])
        lf=mmr_leaf(i,x["bp_id"],x["bp_root"],fsha);leaves.append(lf)
        mr,_=mmr_root(leaves)
        if mr!=x["mmr_root_after"]:raise RuntimeError("mmr mismatch "+x["bp_id"])
    return len(leaves),mmr_root(leaves)[0]

def main():
    os.chdir(ROOT)
    if (ROOT/".venv").exists():
        import shutil;shutil.rmtree(ROOT/".venv",ignore_errors=True)
    verify_current_parent()
    e.git_clean_except(["scripts/e1r_resume_parallel.py"])
    e.status("EXECUTION_AMENDMENT_EQUIVALENCE","RUNNING")

    # Representative exact-output equivalence before changing execution strategy.
    rule=30
    seq=screen_one(rule)
    with ProcessPoolExecutor(max_workers=1) as ex:
        par=next(ex.map(screen_one,[rule],chunksize=1))
    sd,pd=exact_digest(seq),exact_digest(par)
    eq=sd==pd
    receipt={
      "schema":"E1R_PARALLEL_EXECUTION_EQUIVALENCE_V1",
      "state":"BYTE_IDENTICAL_PASS" if eq else "FAIL",
      "rule":rule,
      "sequential_sha256":sd,
      "parallel_sha256":pd,
      "scientific_design_mutated":False,
      "seed_contract_mutated":False,
      "metrics_mutated":False,
      "pre_result_attempt":{
        "state":"ABORTED_FOR_PERFORMANCE_BEFORE_RESULT_SERIALIZATION",
        "last_reported_rule_completed":32,
        "elapsed_seconds_at_last_report":165.1,
        "result_breakpoint_created":False
      },
      "parallel_workers":min(8,max(2,os.cpu_count() or 2))
    }
    e.write_json("evidence/e1r/PARALLEL_EXECUTION_EQUIVALENCE.json",receipt)
    e.write_text("docs/prereg/E1R_EXECUTION_IMPLEMENTATION_AMENDMENT.md",
      "# E1R execution implementation amendment\n\n"
      "The preregistered scientific design, seeds, metrics, conditions, selection policy and hypothesis rules are unchanged. "
      "The first sequential pilot attempt was stopped before result serialization after the progress monitor reported rule 32 at 165.1 s. "
      "The successor uses multiprocessing across independent rule IDs. Executor.map preserves rule order. "
      "A representative rule is recomputed sequentially and in a spawned worker; continuation requires byte-identical output.\n")
    if not eq:raise RuntimeError("parallel equivalence gate failed")
    bp34=e.make_bp("e1r-execution-amendment","EXECUTION_PARALLELIZATION_BYTE_IDENTICAL_EQUIVALENCE",
      [e.atom_record("evidence/e1r/PARALLEL_EXECUTION_EQUIVALENCE.json","ExecutionReceiptFCO","amendment"),
       e.atom_record("docs/prereg/E1R_EXECUTION_IMPLEMENTATION_AMENDMENT.md","PreregistrationAmendmentFCO","amendment"),
       e.atom_record("scripts/e1r_resume_parallel.py","CodeFCO","code")],
      {"stage":"E1R_EXECUTION_IMPLEMENTATION_AMENDMENT","scientific_design_mutated":False,"equivalence":"BYTE_IDENTICAL_PASS"},
      "e1r: admit byte-identical parallel execution amendment",
      ["evidence/e1r/PARALLEL_EXECUTION_EQUIVALENCE.json","docs/prereg/E1R_EXECUTION_IMPLEMENTATION_AMENDMENT.md","scripts/e1r_resume_parallel.py"])

    e.status("SCREEN_ALL_256_RULES","RUNNING",execution="parallel")
    hrows=[];vrows=[];temporal=[];t0=time.time();workers=receipt["parallel_workers"]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for idx,(rule,h,v,t) in enumerate(ex.map(screen_one,range(256),chunksize=1),1):
            hrows.extend(h);vrows.extend(v);temporal.extend(t)
            if idx%16==0:
                e.status("SCREEN_ALL_256_RULES","RUNNING",rule_completed=rule,rules_done=idx,
                         elapsed_s=round(time.time()-t0,1),workers=workers)
    perf=e.aggregate_screen(hrows,vrows)
    shortlists,global_shortlist=e.pareto_shortlists(perf)
    ds="E1R_ALL256_SCREEN_PILOT_V1";base="data/e1r/"+ds
    e.write_jsonl_gz(base+"/horizontal_rows.jsonl.gz",hrows)
    e.write_jsonl_gz(base+"/vertical_rows.jsonl.gz",vrows)
    e.write_jsonl_gz(base+"/anticube_temporal_aggregate.jsonl.gz",temporal)
    e.write_jsonl(base+"/rule_context_performance.jsonl",perf)
    e.write_json(base+"/PARETO_RULE_SETS.json",{"schema":"E1R_PARETO_RULE_SETS_V1","contexts":shortlists,"global_shortlist":global_shortlist})
    screen={"schema":"E1R_ALL256_SCREEN_SUMMARY_V1","rules":256,"horizontal_case_rows":len(hrows),
      "vertical_case_rows":len(vrows),"total_case_rows":len(hrows)+len(vrows),
      "neutral_base_contexts":256*len(e.STRATA)*len(e.PILOT_REPS),"elapsed_seconds":round(time.time()-t0,3),
      "parallel_workers":workers,"global_shortlist":global_shortlist,"delta_g_star":"NOT_COMPUTED",
      "model_calls":0,"classification":"SCREENING_EXPLORATORY",
      "world_state_vs_observation_history":"separate endpoints"}
    e.write_json(base+"/SCREEN_SUMMARY.json",screen)
    cfg=json.loads((ROOT/"schemas/e1r/E1R_SCREEN_CONFIG_V1.json").read_text())
    mf=e.make_manifest(ds,[base+"/horizontal_rows.jsonl.gz",base+"/vertical_rows.jsonl.gz",
      base+"/anticube_temporal_aggregate.jsonl.gz",base+"/rule_context_performance.jsonl",
      base+"/PARETO_RULE_SETS.json",base+"/SCREEN_SUMMARY.json"],cfg,
      "screening all-256 restoration/context evidence; no universal-best-rule claim")
    e.write_json(base+"/MANIFEST.json",mf)
    e.write_json("RULE_CONTEXT_REGISTRY.json",{"schema":"RULE_CONTEXT_REGISTRY_V1","dataset_id":ds,
      "dataset_root":mf["fmo_root"],"contexts":shortlists,"global_shortlist":global_shortlist})
    e.write_json("RESTORATION_RESULT_REGISTRY.json",{"schema":"RESTORATION_RESULT_REGISTRY_V1",
      "dataset_id":ds,"dataset_root":mf["fmo_root"],"definitions":"schemas/e1r/E1R_RESTORATION_DEFINITIONS_V1.json",
      "screen_summary":screen})
    bp35=e.make_bp("e1r-all256-result","ALL_256_SINGLE_RULE_SCREEN_COMPLETE",
      [e.atom_record(base+"/MANIFEST.json","DatasetManifestFCO","dataset"),
       e.atom_record(base+"/SCREEN_SUMMARY.json","ResultSummaryFCO","result"),
       e.atom_record(base+"/PARETO_RULE_SETS.json","DerivedEvidenceFCO","result"),
       e.atom_record(base+"/rule_context_performance.jsonl","DerivedEvidenceFCO","result"),
       e.atom_record("RULE_CONTEXT_REGISTRY.json","RegistryFCO","result"),
       e.atom_record("RESTORATION_RESULT_REGISTRY.json","RegistryFCO","result")],
      {"stage":"E1R_ALL256_RESULT","dataset_id":ds,"dataset_root":mf["fmo_root"],
       "total_case_rows":len(hrows)+len(vrows),"classification":"SCREENING_EXPLORATORY",
       "model_calls":0,"delta_g_star":"NOT_COMPUTED","execution_amendment":bp34["bp_id"]},
      "e1r: complete all-256 restoration screen",
      [base,"RULE_CONTEXT_REGISTRY.json","RESTORATION_RESULT_REGISTRY.json"])
    e.status("SCREEN_ALL_256_RULES","PASS",dataset_root=mf["fmo_root"],
             total_case_rows=len(hrows)+len(vrows),elapsed_s=screen["elapsed_seconds"])

    plan={"schema":"E1R_RULE_SELECTION_CONFIRMATORY_V1","source_screen_breakpoint":bp35["bp_id"],
      "fresh_replicates":list(e.CONFIRM_REPS),"contexts":shortlists,"global_shortlist":global_shortlist,
      "arms":["CONTEXT_SELECTED_RULE","BEST_GLOBAL_TRAIN_RULE","RANDOM_RULE"],
      "primary_metric":"antidote_gain_vs_sham in mean post-intervention normalized Hamming divergence",
      "primary_test":"paired deterministic sign-flip permutation, 10000 draws; Holm over 12 horizontal contexts",
      "pilot_reuse":"pilot selects candidates only; fresh replicate IDs provide confirmation"}
    e.write_json("docs/prereg/E1R_RULE_SELECTION_CONFIRMATORY.json",plan)
    bp36=e.make_bp("e1r-rule-selection-prereg","RULE_SELECTION_CONFIRMATORY_PREREGISTERED",
      [e.atom_record("docs/prereg/E1R_RULE_SELECTION_CONFIRMATORY.json","PreregistrationFCO","prereg"),
       e.atom_record(base+"/PARETO_RULE_SETS.json","ScreeningEvidenceFCO","screening"),
       e.atom_record("RULE_CONTEXT_REGISTRY.json","RegistryFCO","screening")],
      {"stage":"E1R_RULE_SELECTION_PREREG","fresh_replicates":len(e.CONFIRM_REPS),"selection_from_test_set":False},
      "e1r: preregister fresh-replicate context rule selection",
      ["docs/prereg/E1R_RULE_SELECTION_CONFIRMATORY.json"])
    e.status("SELECT_CONTEXTUAL_SIGNAL","RUNNING")
    confrows,confctx,confover=e.run_confirmatory(shortlists,global_shortlist)
    cbase="data/e1r/E1R_RULE_SELECTION_CONFIRMATORY_V1"
    e.write_jsonl_gz(cbase+"/rows.jsonl.gz",confrows);e.write_json(cbase+"/CONTEXT_RESULTS.json",confctx);e.write_json(cbase+"/RESULT.json",confover)
    cmf=e.make_manifest("E1R_RULE_SELECTION_CONFIRMATORY_V1",
      [cbase+"/rows.jsonl.gz",cbase+"/CONTEXT_RESULTS.json",cbase+"/RESULT.json"],plan,
      "fresh-replicate context-selected vs global/random ECA transform comparison")
    e.write_json(cbase+"/MANIFEST.json",cmf)
    bp37=e.make_bp("e1r-rule-selection-result","RULE_SELECTION_CONFIRMATORY_COMPLETE",
      [e.atom_record(cbase+"/MANIFEST.json","DatasetManifestFCO","dataset"),
       e.atom_record(cbase+"/RESULT.json","ClaimDecisionFCO","result"),
       e.atom_record(cbase+"/CONTEXT_RESULTS.json","DerivedEvidenceFCO","result")],
      {"stage":"E1R_RULE_SELECTION_RESULT","dataset_root":cmf["fmo_root"],"claim_state":confover["state"],
       "model_calls":0,"delta_g_star":"NOT_COMPUTED"},
      "e1r: complete fresh-replicate context rule selection",[cbase])
    e.status("SELECT_CONTEXTUAL_SIGNAL","PASS",claim_state=confover["state"],result=confover)

    compplan={"schema":"E1R_RULE_COMPOSITION_SCREEN_V1","source_selection_breakpoint":bp37["bp_id"],
      "candidate_policy":"top 4 from each frozen context shortlist","ordered_pairs":"all 4x4, including same-rule twice",
      "fresh_replicates":list(e.COMPOSITION_REPS),"steps_per_rule":4,
      "endpoint":"final normalized Hamming divergence to same-order clean reference",
      "classification":"SCREENING_EXPLORATORY","confirmatory_claim":False}
    e.write_json("docs/prereg/E1R_RULE_COMPOSITION.json",compplan)
    bp38=e.make_bp("e1r-rule-composition-prereg","RULE_COMPOSITION_SCREEN_PREREGISTERED",
      [e.atom_record("docs/prereg/E1R_RULE_COMPOSITION.json","PreregistrationFCO","prereg"),
       e.atom_record("RULE_CONTEXT_REGISTRY.json","RegistryFCO","source")],
      {"stage":"E1R_RULE_COMPOSITION_PREREG","top_k":e.K_COMPOSITION},
      "e1r: preregister ordered rule-composition screen",["docs/prereg/E1R_RULE_COMPOSITION.json"])
    e.status("TEST_ORDER_CROSSES","RUNNING")
    comprows,compsum=e.run_composition(shortlists)
    obase="data/e1r/E1R_RULE_COMPOSITION_SCREEN_V1"
    e.write_jsonl_gz(obase+"/rows.jsonl.gz",comprows);e.write_jsonl(obase+"/pair_context_summary.jsonl",compsum)
    osum={"schema":"E1R_RULE_COMPOSITION_SUMMARY_V1","rows":len(comprows),
      "mean_order_abs_effect":float(np.mean([x["mean_order_abs_effect"] for x in compsum])),
      "cells_with_noncommutativity":sum(x["noncommutative_fraction"]>0 for x in compsum),
      "context_pair_cells":len(compsum)}
    e.write_json(obase+"/SUMMARY.json",osum)
    omf=e.make_manifest("E1R_RULE_COMPOSITION_SCREEN_V1",
      [obase+"/rows.jsonl.gz",obase+"/pair_context_summary.jsonl",obase+"/SUMMARY.json"],compplan,
      "screening ordered rule-composition evidence; no global-best claim")
    e.write_json(obase+"/MANIFEST.json",omf)
    bp39=e.make_bp("e1r-rule-composition-result","RULE_COMPOSITION_SCREEN_COMPLETE",
      [e.atom_record(obase+"/MANIFEST.json","DatasetManifestFCO","dataset"),
       e.atom_record(obase+"/SUMMARY.json","ResultSummaryFCO","result"),
       e.atom_record(obase+"/pair_context_summary.jsonl","DerivedEvidenceFCO","result")],
      {"stage":"E1R_RULE_COMPOSITION_RESULT","dataset_root":omf["fmo_root"],"classification":"SCREENING_EXPLORATORY"},
      "e1r: complete ordered rule-composition screen",[obase])

    orders=[
      {"id":"O_ECA_THEN_ANTICUBE","pipeline":["SOURCE","ECA","ANTICUBE","CONTEXTPACKET"],
       "state":"EXECUTED_IN_E1R_SCREEN","type_valid":True},
      {"id":"O_ANTICUBE_THEN_ECA","pipeline":["SOURCE","ANTICUBE","ECA","CONTEXTPACKET"],
       "state":"ABSTAIN_TYPE_ERROR","type_valid":False,
       "note":"No frozen projection maps a five-state probability vector back to an ECA binary lattice."},
      {"id":"O_ECA_THEN_DELTAGSTAR_THEN_ANTICUBE","state":"NOT_TESTED_DELTAGSTAR_NOT_COMPUTED","type_valid":None},
      {"id":"O_RAW_CONTEXT","pipeline":["SOURCE","CONTEXTPACKET"],"state":"VALID_CONTROL","type_valid":True}]
    e.write_json("TRANSFORM_ORDER_REGISTRY.json",{"schema":"TRANSFORM_ORDER_REGISTRY_V1","orders":orders,
      "commutativity_claim":"not assumed; ordered ECA pairs empirically screened"})
    bp40=e.make_bp("e1r-transform-order-prereg","TRANSFORM_ORDER_TYPE_PROTOCOL_FROZEN",
      [e.atom_record("TRANSFORM_ORDER_REGISTRY.json","TransformOrderRegistryFCO","order")],
      {"stage":"E1R_TRANSFORM_ORDER_PREREG","delta_g_star":"NOT_COMPUTED"},
      "e1r: freeze transform-order type protocol",["TRANSFORM_ORDER_REGISTRY.json"])
    e.write_json("evidence/e1r/TRANSFORM_ORDER_RESULT.json",
      {"schema":"E1R_TRANSFORM_ORDER_RESULT_V1","orders":orders,
       "ordered_rule_pair_dataset":"E1R_RULE_COMPOSITION_SCREEN_V1",
       "finding":"rule-pair order evaluated empirically; Anticube-before-ECA rejected as type error absent frozen projection",
       "claim_ceiling":"type safety/order sensitivity only; no causal claim"})
    bp41=e.make_bp("e1r-transform-order-result","TRANSFORM_ORDER_RESULT_COMPLETE",
      [e.atom_record("evidence/e1r/TRANSFORM_ORDER_RESULT.json","ResultFCO","result"),
       e.atom_record("TRANSFORM_ORDER_REGISTRY.json","TransformOrderRegistryFCO","result")],
      {"stage":"E1R_TRANSFORM_ORDER_RESULT"},"e1r: record transform-order result",
      ["evidence/e1r/TRANSFORM_ORDER_RESULT.json"])

    by=defaultdict(list)
    for x in temporal:by[(x["condition"],x["time"])].append(x["anticube_mean"])
    antirows=[]
    for (cond,t),xs in sorted(by.items()):
        antirows.append({"condition":cond,"time":t,**{k:float(np.mean([z[k] for z in xs]))
          for k in ("SELF_SAFE","SELF_UNSAFE","NONSELF_SAFE","NONSELF_UNSAFE","UNKNOWN")}})
    e.write_jsonl("evidence/e1r/ANTICUBE_TEMPORAL_RESULT.jsonl",antirows)
    e.write_json("evidence/e1r/ANTICUBE_TEMPORAL_SUMMARY.json",
      {"schema":"E1R_ANTICUBE_TEMPORAL_SUMMARY_V1","rows":len(antirows),
       "mapping":"PUBLIC_SIMULATION_ANTICUBE_E1R_V1","calibration":"NOT_INDEPENDENTLY_VALIDATED",
       "claim_ceiling":"descriptive simulation trajectory only"})
    bp42=e.make_bp("e1r-anticube-temporal","ANTICUBE_TEMPORAL_ANALYSIS_COMPLETE",
      [e.atom_record("evidence/e1r/ANTICUBE_TEMPORAL_RESULT.jsonl","DerivedEvidenceFCO","anticube"),
       e.atom_record("evidence/e1r/ANTICUBE_TEMPORAL_SUMMARY.json","ResultSummaryFCO","anticube"),
       e.atom_record("schemas/e1r/PUBLIC_SIMULATION_ANTICUBE_E1R_V1.json","SchemaFCO","anticube")],
      {"stage":"E1R_ANTICUBE_TEMPORAL","independent_calibration":False},
      "e1r: freeze Anticube temporal analysis",
      ["evidence/e1r/ANTICUBE_TEMPORAL_RESULT.jsonl","evidence/e1r/ANTICUBE_TEMPORAL_SUMMARY.json"])

    dg={"schema":"E1R_DELTAGSTAR_RECEIPT_V1","state":"NOT_COMPUTED",
        "reason":"No governed private DeltaGStar implementation is present; PUBLIC_CANDIDATE_DELTAGSTAR_V1 is not substituted.",
        "public_candidate_present":"src/daisy/deltag_candidate.py","substitution_performed":False}
    e.write_json("evidence/e1r/DELTAGSTAR_NOT_COMPUTED_RECEIPT.json",dg)
    bp43=e.make_bp("e1r-deltagstar-state","DELTAGSTAR_NOT_COMPUTED",
      [e.atom_record("evidence/e1r/DELTAGSTAR_NOT_COMPUTED_RECEIPT.json","ExecutionReceiptFCO","delta_g")],
      {"stage":"E1R_DELTAGSTAR","delta_g_star":"NOT_COMPUTED"},
      "e1r: preserve DeltaGStar as not computed",["evidence/e1r/DELTAGSTAR_NOT_COMPUTED_RECEIPT.json"])

    runtime=ROOT/"evidence/openjev/RUNTIME_MANIFEST.json";openstate="NOT_TESTED_RUNTIME_NOT_FROZEN"
    if runtime.exists():
        try:
            m=json.loads(runtime.read_text())
            openstate="AVAILABLE_NOT_EXECUTED" if m.get("OPENJEV_LOADED")=="YES" else "NOT_TESTED_RUNTIME_NOT_LOADED"
        except Exception:openstate="NOT_TESTED_RUNTIME_MANIFEST_INVALID"
    comps=[
      {"id":"D0_DETERMINISTIC_ORACLE","state":"EXECUTED","calls":0},
      {"id":"D1_VITHIA_DETERMINISTIC_CONTEXT_POLICY","state":"EXECUTED","calls":0},
      {"id":"D2_OPENJEV_LOCAL","state":openstate,"provider_label":"OPENJEV_LOCAL_STANDIN","calls":0},
      {"id":"D3_JEV_HOSTED","state":"NOT_TESTED","calls":0},
      {"id":"D4_LIQUID_LOCAL","state":"NOT_TESTED","calls":0},
      {"id":"D5_OLLAMA_OLLARMA","state":"NOT_TESTED","calls":0}]
    e.write_json("SYSTEM1_COMPARATOR_REGISTRY.json",
      {"schema":"SYSTEM1_COMPARATOR_REGISTRY_V1","comparators":comps,
       "same_contextpacket_requirement":True,"model_weight_updates":False})
    bp44=e.make_bp("e1r-system1-runtime","SYSTEM1_COMPARATOR_RUNTIME_STATE_FROZEN",
      [e.atom_record("SYSTEM1_COMPARATOR_REGISTRY.json","ComparatorRegistryFCO","system1"),
       e.atom_record("evidence/openjev/UPSTREAM_IDENTITY.json","ExternalModelIdentityFCO","system1")],
      {"stage":"E1R_SYSTEM1_RUNTIME_FREEZE","openjev_state":openstate,"model_calls":0},
      "e1r: freeze System-1 comparator availability",["SYSTEM1_COMPARATOR_REGISTRY.json"])
    e.write_json("evidence/e1r/SYSTEM1_PORTABILITY_RESULT.json",
      {"schema":"E1R_SYSTEM1_PORTABILITY_RESULT_V1","state":"PARTIAL_DETERMINISTIC_ONLY",
       "executed":["D0_DETERMINISTIC_ORACLE","D1_VITHIA_DETERMINISTIC_CONTEXT_POLICY"],
       "not_tested":["D2_OPENJEV_LOCAL","D3_JEV_HOSTED","D4_LIQUID_LOCAL","D5_OLLAMA_OLLARMA"],
       "reason":"No frozen loaded OpenJEV runtime in this branch; external/local model calls not initiated."})
    bp45=e.make_bp("e1r-system1-portability","SYSTEM1_PORTABILITY_PARTIAL_DETERMINISTIC_ONLY",
      [e.atom_record("evidence/e1r/SYSTEM1_PORTABILITY_RESULT.json","ResultFCO","system1"),
       e.atom_record("SYSTEM1_COMPARATOR_REGISTRY.json","ComparatorRegistryFCO","system1")],
      {"stage":"E1R_SYSTEM1_PORTABILITY_RESULT","model_calls":0},
      "e1r: record partial deterministic System-1 comparison",
      ["evidence/e1r/SYSTEM1_PORTABILITY_RESULT.json"])

    vcc=e.scan_vcc();e.write_json("VCC_TRANSLATION_REGISTRY.json",vcc)
    e.write_text("docs/prereg/E1R_VCC_TRANSLATION.md",
      "# E1R to VCC computational translation\n\nEvidence level: SIMULATED_COMPUTATIONAL_TRANSFORM_OF_BIOLOGICAL_DATA. "
      "No ECA rule is a biological mechanism claim. Execution requires exact recovery of governed VCC data, contexts, "
      "perturbations, frozen splits, current baseline/nulls and custody receipts.\n")
    bp46=e.make_bp("e1r-vcc-translation-prereg","VCC_TRANSLATION_PREREGISTERED_EXECUTION_DEFERRED",
      [e.atom_record("VCC_TRANSLATION_REGISTRY.json","RegistryFCO","vcc"),
       e.atom_record("docs/prereg/E1R_VCC_TRANSLATION.md","PreregistrationFCO","vcc")],
      {"stage":"E1R_VCC_TRANSLATION_PREREG","vcc_state":vcc["state"],"biological_mechanism_claim":False},
      "e1r: preregister bounded VCC computational translation",
      ["VCC_TRANSLATION_REGISTRY.json","docs/prereg/E1R_VCC_TRANSLATION.md"])

    figs=e.build_figures(perf,shortlists,confctx,compsum,temporal)
    e.write_json("evidence/e1r/FIGURE_BUILD_RECEIPT.json",figs)
    tdir=ROOT/"tables/e1r";tdir.mkdir(parents=True,exist_ok=True)
    h=[x for x in perf if x["context_type"]=="HORIZONTAL"];rg=defaultdict(list)
    for x in h:rg[x["rule_id"]].append(x)
    all256=[{"rule_id":r,"mean_gain_vs_sham":float(np.mean([x["antidote_gain_vs_sham"] for x in rs])),
      "mean_exact_rate":float(np.mean([x["antidote_exact_rate"] for x in rs])),
      "mean_context_rate":float(np.mean([x["antidote_context_rate"] for x in rs])),
      "mean_functional_rate":float(np.mean([x["antidote_functional_rate"] for x in rs])),
      "mean_neutral_entropy":float(np.mean([x["neutral_entropy"] for x in rs])),
      "mean_harm_rate":float(np.mean([x["antidote_harm_rate"] for x in rs]))} for r,rs in sorted(rg.items())]
    tables={
      "T-E1R-1_all256_rule_summary.csv":all256,
      "T-E1R-2_context_pareto.csv":[{"context":c,"pareto_rules":v["pareto_rules"],"shortlist":v["shortlist"]} for c,v in shortlists.items()],
      "T-E1R-3_restoration_definitions.csv":[
        {"metric":"R_EXACT","definition":"bitwise equality"},
        {"metric":"R_SHIFT","definition":"zero Hamming under shifts -3..3"},
        {"metric":"R_CONTEXT","definition":"same frozen density/transition bins"},
        {"metric":"R_FUNCTIONAL","definition":"same safe-action signature"},
        {"metric":"R_TRAJECTORY","definition":"normalized Hamming divergence/AUD"}],
      "T-E1R-4_confirmatory_statistics.csv":confctx,
      "T-E1R-5_rule_composition.csv":compsum,
      "T-E1R-6_transform_order.csv":orders,
      "T-E1R-7_system1_comparators.csv":comps,
      "T-VCC-1_arms.csv":vcc["arms"],
      "T-LIMIT.csv":[{"item":"DeltaGStar","state":"NOT_COMPUTED"},{"item":"OpenJEV","state":openstate},
                     {"item":"Hosted JEV","state":"NOT_TESTED"},{"item":"VCC translation","state":vcc["state"]},
                     {"item":"Wolfram class labels","state":"UNKNOWN_NOT_INGESTED"}]}
    for name,rows in tables.items():e.csv_file("tables/e1r/"+name,rows)
    table_files=sorted(str(p.relative_to(ROOT)) for p in tdir.glob("*.csv"))

    led=json.loads((ROOT/"governance/MMR_LEDGER.json").read_text());last=led["entries"][-1]
    handoff={"schema":"E1R_DAISY_HANDOFF_V1",
      "current_parent_state":{"commit":e.PARENT_COMMIT,"breakpoint":e.PARENT_BP,"mmr_root":e.PARENT_MMR_ROOT},
      "branch":e.BRANCH,"all_256_screen_state":"COMPLETE_SCREENING",
      "total_runs":{"horizontal_case_rows":len(hrows),"vertical_case_rows":len(vrows),
                    "pilot_total_case_rows":len(hrows)+len(vrows),
                    "confirmatory_rows":len(confrows),"composition_rows":len(comprows)},
      "rule_context_dataset_id":ds,"rule_context_dataset_root":mf["fmo_root"],
      "neutral_results":"paired same-rule neutral reference in each horizontal condition",
      "horizontal_poison_results":base+"/rule_context_performance.jsonl",
      "vertical_history_poison_results":base+"/rule_context_performance.jsonl",
      "sham_results":base+"/horizontal_rows.jsonl.gz","antidote_results":base+"/horizontal_rows.jsonl.gz",
      "exact_restoration_results":base+"/rule_context_performance.jsonl",
      "contextual_restoration_results":base+"/rule_context_performance.jsonl",
      "functional_restoration_results":base+"/rule_context_performance.jsonl",
      "top_context_rules":"RULE_CONTEXT_REGISTRY.json","pareto_rule_sets":base+"/PARETO_RULE_SETS.json",
      "rule_selection_result":confover,"rule_pair_results":obase+"/pair_context_summary.jsonl",
      "order_cross_results":"evidence/e1r/TRANSFORM_ORDER_RESULT.json",
      "anticube_temporal_results":"evidence/e1r/ANTICUBE_TEMPORAL_RESULT.jsonl",
      "delta_g_star_state":"NOT_COMPUTED","openjev_state":openstate,"jev_state":"NOT_TESTED",
      "vithia_comparator_state":"EXECUTED_DETERMINISTIC_CONTEXT_POLICY",
      "vcc_translation_state":vcc["state"],
      "nulls":[x for x in confctx if x["state"]=="FAIL_TO_REJECT_H0"],
      "negatives":[x for x in confctx if x["state"]=="NEGATIVE"],
      "abstains":[{"id":"O_ANTICUBE_THEN_ECA","state":"ABSTAIN_TYPE_ERROR"}],
      "not_tested":["DELTAGSTAR","JEV_HOSTED","LIQUID_LOCAL","OLLAMA_OLLARMA","VCC_EXECUTION"]+
                   ([] if openstate.startswith("AVAILABLE") else ["OPENJEV_LOCAL"]),
      "breakpoints_created":[x["bp_id"] for x in led["entries"] if int(x["bp_id"].split("-")[-1])>=29],
      "mmr_size_before_handoff":last["mmr_size"],"mmr_root_before_handoff":last["mmr_root_after"],
      "signature_state":"NOT_SIGNED","figures":figs,"tables":table_files,
      "next_action":"Optionally freeze/load OpenJEV for matched ContextPacket comparison; separately recover canonical VCC repo/splits before VCC execution."}
    e.write_json("E1R_DAISY_HANDOFF.json",handoff)
    atoms=[
      e.atom_record("E1R_DAISY_HANDOFF.json","HandoffFCO","handoff"),
      e.atom_record("RULE_CONTEXT_REGISTRY.json","RegistryFCO","handoff"),
      e.atom_record("RULE_FCO_REGISTRY.json","RegistryFCO","handoff"),
      e.atom_record("RESTORATION_RESULT_REGISTRY.json","RegistryFCO","handoff"),
      e.atom_record("TRANSFORM_ORDER_REGISTRY.json","RegistryFCO","handoff"),
      e.atom_record("SYSTEM1_COMPARATOR_REGISTRY.json","RegistryFCO","handoff"),
      e.atom_record("VCC_TRANSLATION_REGISTRY.json","RegistryFCO","handoff"),
      e.atom_record("evidence/e1r/FIGURE_BUILD_RECEIPT.json","ExecutionReceiptFCO","handoff")]
    for p in figs.get("files",[]):atoms.append(e.atom_record(p,"FigureFCO","figures"))
    for p in table_files:atoms.append(e.atom_record(p,"TableFCO","tables"))
    bp47=e.make_bp("e1r-handoff","E1R_DAISY_SUCCESSOR_COMPLETE_BOUNDED",atoms,
      {"stage":"E1R_FINAL_HANDOFF","all256_screen":"COMPLETE_SCREENING",
       "rule_selection":confover["state"],"rule_composition":"COMPLETE_SCREENING",
       "delta_g_star":"NOT_COMPUTED","openjev":openstate,"vcc_translation":vcc["state"],
       "signature_state":"NOT_SIGNED"},
      "e1r: seal all-256 restoration successor handoff",
      ["E1R_DAISY_HANDOFF.json","RULE_CONTEXT_REGISTRY.json","RULE_FCO_REGISTRY.json",
       "RESTORATION_RESULT_REGISTRY.json","TRANSFORM_ORDER_REGISTRY.json",
       "SYSTEM1_COMPARATOR_REGISTRY.json","VCC_TRANSLATION_REGISTRY.json",
       "evidence/e1r/FIGURE_BUILD_RECEIPT.json","figures/e1r","tables/e1r"])

    size,root=final_verify(34)
    env={**os.environ,"PYTHONPATH":str(ROOT),"PYTHONDONTWRITEBYTECODE":"1"}
    e.run([str(e.SHARED_PY),"-m","pytest","-q"],env=env)
    e.run([str(e.SHARED_PY),"scripts/secret_scan.py"],env=env)
    e.status("FINAL","PASS",head=e.run(["git","rev-parse","HEAD"],capture=True).stdout.strip(),
             mmr_size=size,mmr_root=root,rule_selection_state=confover["state"],
             openjev_state=openstate,vcc_state=vcc["state"])
    print("E1R_COMPLETE=YES")
    print("HEAD="+e.run(["git","rev-parse","HEAD"],capture=True).stdout.strip())
    print("MMR_SIZE="+str(size));print("MMR_ROOT="+root)
    print("RULE_CONTEXT_DATASET_ROOT="+mf["fmo_root"])
    print("RULE_SELECTION_STATE="+confover["state"])
    print("DELTAGSTAR_STATE=NOT_COMPUTED");print("OPENJEV_STATE="+openstate)
    print("VCC_TRANSLATION_STATE="+vcc["state"]);print("SIGNATURE_STATE=NOT_SIGNED")

if __name__=="__main__":
    try:main()
    except Exception as exc:
        e.status("FAILED","FAIL",error=repr(exc))
        raise
