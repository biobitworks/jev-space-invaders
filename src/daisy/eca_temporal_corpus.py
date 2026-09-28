"""Temporal, transposition-merged ECA action graph for Vithia training-candidate data.

This is a successor to the root-summary Daisy corpus. It stores every unique live
decision node at every depth and every outgoing LEFT/STAY/RIGHT intervention.
The graph preserves path multiplicity, so all raw action strings are represented
without duplicating equivalent simulator states.
"""
from __future__ import annotations
from functools import lru_cache
from src.daisy import eca_corpus as e
from src.s01.canon import write_jsonl, write_manifest

DATASET_ID="VITHIA_DAISY_ECA_TEMPORAL_ACTION_GRAPH_V1"
H=e.H_ORACLE
CODE=["src/daisy/eca_temporal_corpus.py","src/daisy/eca_corpus.py",
      "src/kernels/eca.py","scripts/build_daisy_eca_temporal.py"]

def graph_rows(rule:int,ic:str,start_x:int):
    world=e.trajectory(rule,ic,H)
    layers=[{start_x:1}]
    for depth in range(H):
        arriving=world[depth+1]
        nxt={}
        for x,mult in layers[depth].items():
            for action in e.ACTIONS:
                nx=min(max(x+e.DX[action],0),e.W-1)
                if arriving[nx]==0:
                    nxt[nx]=nxt.get(nx,0)+mult
        layers.append(nxt)

    @lru_cache(maxsize=None)
    def safe_paths(depth,x):
        if depth==H:
            return 1
        arriving=world[depth+1]
        total=0
        for action in e.ACTIONS:
            nx=min(max(x+e.DX[action],0),e.W-1)
            if arriving[nx]==0:
                total+=safe_paths(depth+1,nx)
        return total

    rows=[]
    for depth in range(H):
        remaining=H-depth
        arriving=world[depth+1]
        for x,multiplicity in sorted(layers[depth].items()):
            sid=e.state_id(rule,world[depth],x)
            vals={}
            succ={}
            for action in e.ACTIONS:
                nx=min(max(x+e.DX[action],0),e.W-1)
                hit=arriving[nx]==1
                count=0 if hit else safe_paths(depth+1,nx)
                vals[action]=count
                succ[action]=(nx,hit,e.state_id(rule,arriving,nx))
            best=max(vals.values())
            optimal=sorted(a for a,v in vals.items() if v==best and v>0)
            total=sum(vals.values())
            for action in e.ACTIONS:
                nx,hit,succ_id=succ[action]
                rows.append({
                    "corpus_id":DATASET_ID,"classification":"TRAINING_CANDIDATE",
                    "split":e.split_of(rule,ic),"rule_id":rule,
                    "rule_orbit_rep":min(e.orbit(rule)),"initial_condition_id":ic,
                    "trajectory_family_id":e.cid({"rule":rule,"ic":ic,"start_x":start_x}),
                    "start_x":start_x,"event_index":depth,"remaining_horizon":remaining,
                    "state_id":sid,"ship_x":x,"hazard_row":list(world[depth]),
                    "path_multiplicity_to_state":multiplicity,
                    "action":action,"successor_state_id":succ_id,"successor_x":nx,
                    "collision":hit,"terminal":hit or depth+1==H,
                    "safe_completion_count":vals[action],
                    "safe_fraction_of_raw_suffix":vals[action]/(len(e.ACTIONS)**(remaining-1)),
                    "path_share_safe_completions":vals[action]/total if total else None,
                    "optimal_action_set":optimal,
                    "regret_safe_completions":best-vals[action],
                    "public_anticube":{
                        "ship_after":{"identity":"SELF","safety":"NONSAFE" if hit else "SAFE"},
                        "target_cell":{"identity":"NONSELF","safety":"NONSAFE" if hit else "SAFE"},
                        "definition":"PUBLIC_OPERATOR_DECLARED_ECA_DODGE_TEMPORAL_V1"},
                    "U_star":0.0 if vals[action]>0 else 1.0,
                    "H_norm":"NOT_COMPUTED","G_star":"NOT_COMPUTED",
                    "delta_G_star":"NOT_COMPUTED","delta_g_definition_id":None})
    naive_prefix_nodes=sum(len(e.ACTIONS)**d for d in range(H+1))
    unique_nodes=sum(len(layer) for layer in layers)
    summary={"rule_id":rule,"initial_condition_id":ic,"start_x":start_x,
             "trajectory_family_id":e.cid({"rule":rule,"ic":ic,"start_x":start_x}),
             "naive_action_prefix_nodes":naive_prefix_nodes,
             "unique_live_nodes":unique_nodes,
             "state_compression_ratio":1-unique_nodes/naive_prefix_nodes,
             "root_safe_action_strings":safe_paths(0,start_x),
             "graph_edge_rows":len(rows)}
    return rows,summary

def build():
    rows=[]
    summaries=[]
    for rule in range(256):
        for ic in e.ICS:
            for start_x in e.STARTS:
                rr,ss=graph_rows(rule,ic,start_x)
                rows.extend(rr)
                summaries.append(ss)
    root=e.ROOT if hasattr(e,"ROOT") else None
    from pathlib import Path
    d=Path(__file__).resolve().parents[2]/"data"/"daisy"/DATASET_ID
    d.mkdir(parents=True,exist_ok=True)
    rows_sha,rows_bytes,nrows=write_jsonl(d/"rows.jsonl",rows)
    sum_sha,sum_bytes,nsum=write_jsonl(d/"graph_summary.jsonl",summaries)
    man=write_manifest(d,dataset_id=DATASET_ID,
        schema="every unique live decision node x every outgoing ECA-dodge action across H=8",
        kind="training_candidate",source="VITHIA_DAISY_ECA_ACTION_CORPUS_V1",
        generation_code=CODE,
        config={"W":e.W,"H":H,"actions":list(e.ACTIONS),"starts":list(e.STARTS),
                "transposition":"same exact ECA hazard row, ship x and event depth",
                "representation":"path multiplicity + graph edges reconstruct raw action-string space",
                "delta_G_star":"NOT_COMPUTED until real decider probabilities exist"},
        seeds={"ics":e.ICS},license="CC-BY-4.0",
        parent_evidence=["VITHIA_DAISY_ECA_ACTION_CORPUS_V1"],
        claim_ceiling="deterministic model-free training candidate; public Anticube labels only; not VITHIA_NATIVE")
    return {"dataset_id":DATASET_ID,"rows":nrows,"rows_sha256":rows_sha,
            "rows_bytes":rows_bytes,"summary_rows":nsum,"summary_sha256":sum_sha,
            "summary_bytes":sum_bytes,"fmo_root":man["fmo_root"],
            "mean_state_compression_ratio":sum(x["state_compression_ratio"] for x in summaries)/len(summaries)}

