#!/usr/bin/env python3
from __future__ import annotations
import csv, gzip, hashlib, json, math, os, random, shutil, subprocess, sys, time
from collections import defaultdict
from pathlib import Path
import numpy as np

ROOT=Path("/Users/byron/projects/active/jev-space-invaders-e1r")
SHARED_PY=Path("/Users/byron/projects/active/jev-space-invaders/.venv/bin/python")
BRANCH="e1r/restoration-rule-context-v01"
PARENT_COMMIT="4c1bbb19b89a7ee1e1dee662cfd0f227186ebafd"
PARENT_BP="UFA-JEV-BP-0028"
PARENT_MMR_ROOT="5f742663f7e0c12e100e292cc794eefb0360a068a5c20c2b1be019ace1cb298b"
STATUS=Path("/tmp/VITHIA_E1R_STATUS.json")
sys.path.insert(0,str(ROOT))
from src.breakpoints import atom_record,create_breakpoint
from src.fmo import fmo_root,leaf,mmr_leaf,mmr_root,sha256_file

W,T,TP,TA=64,48,16,24
SEVERITIES=(0.05,0.10,0.20)
STRATA=("single","sparse","balanced","dense")
PILOT_REPS=tuple(range(20))
CONFIRM_REPS=tuple(range(100,130))
COMPOSITION_REPS=tuple(range(200,210))
VERT_OPS=("missing","bit_flip")
SHIFTS=tuple(range(-3,4))
K_SHORTLIST,K_COMPOSITION=8,4
RULE_TABLE=np.array([[(r>>i)&1 for i in range(8)] for r in range(256)],dtype=np.uint8)

def run(cmd,check=True,capture=False,cwd=ROOT,env=None):
    p=subprocess.run(cmd,cwd=cwd,text=True,capture_output=capture,env=env)
    if check and p.returncode:
        raise RuntimeError("command failed rc=%d: %r\n%s\n%s"%(p.returncode,cmd,p.stdout or "",p.stderr or ""))
    return p

def status(stage,state,**extra):
    obj={"project":"VITHIA_SPACE","task":"VITHIA_E1R_RULE_CONTEXT_RESTORATION_AND_VCC_TRANSLATION_SUCCESSOR",
         "branch":BRANCH,"parent_commit":PARENT_COMMIT,"parent_breakpoint":PARENT_BP,
         "stage":stage,"state":state,"utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),**extra}
    STATUS.write_text(json.dumps(obj,indent=2)+"\n")
    print("STATUS "+json.dumps(obj,sort_keys=True),flush=True)

def cbytes(obj):
    return json.dumps(obj,sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode()

def cid(obj):
    return "sha256:"+hashlib.sha256(cbytes(obj)).hexdigest()

def sha_file(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for b in iter(lambda:f.read(1<<20),b""): h.update(b)
    return h.hexdigest()

def seed_int(*parts):
    return int.from_bytes(hashlib.sha256("|".join(map(str,parts)).encode()).digest()[:8],"big")&0x7fffffff

def write_json(rel,obj):
    p=ROOT/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,indent=2,sort_keys=True)+"\n")

def write_text(rel,text):
    p=ROOT/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)

def write_jsonl(rel,rows):
    p=ROOT/rel;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("wb") as f:
        for r in rows:f.write(cbytes(r)+b"\n")
    return sha_file(p),p.stat().st_size

def write_jsonl_gz(rel,rows):
    p=ROOT/rel;p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("wb") as raw:
        with gzip.GzipFile(fileobj=raw,mode="wb",mtime=0) as gz:
            for r in rows:gz.write(cbytes(r)+b"\n")
    return sha_file(p),p.stat().st_size

def make_manifest(dataset_id,files,config,ceiling):
    groups={"data":[]};recs=[]
    for rel in sorted(files):
        p=ROOT/rel;sha,n=sha256_file(p);recs.append({"path":rel,"bytes":n,"sha256":sha});groups["data"].append((rel,leaf(rel,n,sha)))
    root,_=fmo_root(groups)
    return {"dataset_id":dataset_id,"kind":"scientific_successor","schema":"E1R_DATASET_MANIFEST_V1",
            "source":"VITHIA_E1R","license":"NOT_ESTABLISHED_FOR_E1R_SUCCESSOR",
            "code_commit_at_generation":run(["git","rev-parse","HEAD"],capture=True).stdout.strip(),
            "config":config,"files":recs,"fmo_root":root,"visibility":"public","claim_ceiling":ceiling}

def git_clean_except(allowed=()):
    bad=[]
    for line in run(["git","status","--porcelain"],capture=True).stdout.splitlines():
        p=line[3:] if len(line)>=4 else line
        if not any(p==a or p.startswith(a.rstrip("/")+"/") for a in allowed):bad.append(line)
    if bad:raise RuntimeError("unexpected dirty worktree: "+repr(bad))

def commit_push(msg,paths):
    run(["git","add",*paths]);run(["git","commit","-m",msg])
    local=run(["git","rev-parse","HEAD"],capture=True).stdout.strip()
    run(["git","push","-u","origin",BRANCH])
    remote=run(["git","ls-remote","origin","refs/heads/"+BRANCH],capture=True).stdout.split()[0]
    if remote!=local:raise RuntimeError("remote mismatch")
    print("REMOTE_VERIFIED="+remote,flush=True);return local

def make_bp(slug,state,atoms,body,msg,paths):
    out=create_breakpoint(slug,state,atoms,{**body,"scientific_parent_commit":PARENT_COMMIT,
        "scientific_parent_breakpoint":PARENT_BP,"scientific_parent_mmr_root":PARENT_MMR_ROOT})
    print("BREAKPOINT "+json.dumps({k:out[k] for k in ("bp_id","bp_root","mmr_size","mmr_root_after")}),flush=True)
    commit_push(msg,paths+["governance"]);return out

def verify_parent_metadata():
    led=json.loads((ROOT/"governance/MMR_LEDGER.json").read_text())
    if led["entries"][-1]["bp_id"]!=PARENT_BP or led["entries"][-1]["mmr_root_after"]!=PARENT_MMR_ROOT:raise RuntimeError("parent ledger mismatch")
    leaves=[];lfs=0
    for i,e in enumerate(led["entries"]):
        p=ROOT/e["bp_file"];fsha,_=sha256_file(p)
        if fsha!=e["bp_file_sha256"]:raise RuntimeError("breakpoint file mismatch "+e["bp_id"])
        if e["root_kind"]=="FMO_V1_BREAKPOINT_ATOMS":
            d=json.loads(p.read_text());groups=defaultdict(list)
            for a in d["atoms"]:
                lf=leaf(a["path"],a["bytes"],a["sha256"])
                if lf.hex()!=a["fmo_leaf"]:raise RuntimeError("leaf mismatch "+a["path"])
                groups[a["group"]].append((a["path"],lf))
                q=ROOT/a["path"]
                if q.exists():
                    data=q.read_bytes()
                    if hashlib.sha256(data).hexdigest()!=a["sha256"] or len(data)!=a["bytes"]:
                        txt=data.decode(errors="ignore")
                        if txt.startswith("version https://git-lfs.github.com/spec/v1"):
                            oid=size=None
                            for line in txt.splitlines():
                                if line.startswith("oid sha256:"):oid=line.split(":",1)[1]
                                if line.startswith("size "):size=int(line.split()[1])
                            if oid==a["sha256"] and size==a["bytes"]:lfs+=1
            root,_=fmo_root(dict(groups))
            if root!=d["bp_root"] or root!=e["bp_root"]:raise RuntimeError("bp root mismatch "+e["bp_id"])
        lf=mmr_leaf(i,e["bp_id"],e["bp_root"],fsha)
        if lf.hex()!=e["mmr_leaf"]:raise RuntimeError("mmr leaf mismatch "+e["bp_id"])
        leaves.append(lf);mr,_=mmr_root(leaves)
        if mr!=e["mmr_root_after"]:raise RuntimeError("mmr root mismatch "+e["bp_id"])
    final,_=mmr_root(leaves)
    if final!=PARENT_MMR_ROOT:raise RuntimeError("parent MMR mismatch")
    return {"mmr_size":len(leaves),"mmr_root":final,"lfs_pointer_only":lfs}

def step_batch(x,rule):
    x=np.asarray(x,dtype=np.uint8);idx=(np.roll(x,1,axis=-1)<<2)|(x<<1)|np.roll(x,-1,axis=-1)
    return RULE_TABLE[int(rule)][idx]

def step_mixed(x,rules):
    x=np.asarray(x,dtype=np.uint8);rules=np.asarray(rules,dtype=np.int64)
    idx=(np.roll(x,1,axis=-1)<<2)|(x<<1)|np.roll(x,-1,axis=-1)
    return RULE_TABLE[rules[:,None],idx]

def initial_batch(stratum,reps):
    out=np.zeros((len(reps),W),dtype=np.uint8)
    for j,rep in enumerate(reps):
        if stratum=="single":out[j,W//2]=1
        else:
            p={"sparse":.10,"balanced":.50,"dense":.90}[stratum];rng=np.random.default_rng(seed_int("E1R","IC",stratum,rep))
            out[j]=(rng.random(W)<p).astype(np.uint8)
    return out

def evolve(init,rule,steps):
    arr=np.empty((steps+1,*init.shape),dtype=np.uint8);arr[0]=init
    for t in range(steps):arr[t+1]=step_batch(arr[t],rule)
    return arr

def infer_rule(obs,true_rule=None):
    scores=np.zeros(256,dtype=np.int64)
    for t in range(obs.shape[0]-1):
        prev=obs[t];nxt=obs[t+1];l=np.roll(prev,1);r=np.roll(prev,-1);valid=(prev>=0)&(l>=0)&(r>=0)&(nxt>=0)
        if not np.any(valid):continue
        idx=(4*l[valid]+2*prev[valid]+r[valid]).astype(np.int64);y=nxt[valid].astype(np.int64)
        counts=np.bincount(idx*2+y,minlength=16).reshape(8,2)
        scores+=(RULE_TABLE*counts[:,0][None,:]+(1-RULE_TABLE)*counts[:,1][None,:]).sum(axis=1)
    m=int(scores.min());ties=np.flatnonzero(scores==m);mp=int(ties[0])
    rank=None if true_rule is None else 1+int(np.sum(scores<scores[int(true_rule)]))
    return mp,int(len(ties)),rank,None if true_rule is None else int(scores[int(true_rule)])

def predicted_row(clean,map_rule,steps):
    x=clean[None,:].copy()
    for _ in range(steps):x=step_mixed(x,np.array([map_rule]))
    return x[0]

def window_indices(start,width):return (start+np.arange(width))%W

def cone_indices(start,width,radius):return np.array(sorted(set((start-radius+q)%W for q in range(width+2*radius))),dtype=int)

def shift_divergence(a,b):
    return np.min(np.stack([np.mean(np.roll(a,s,axis=-1)!=b,axis=-1) for s in SHIFTS],axis=0),axis=0)

def context_class(x):
    dens=x.mean(axis=-1);trans=np.mean(x!=np.roll(x,-1,axis=-1),axis=-1)
    return np.minimum(19,np.floor(dens*20).astype(int)),np.minimum(19,np.floor(trans*20).astype(int))

def functional_sig(x):
    bits=[]
    for s in (W//4,W//2,3*W//4):
        for dx in (-1,0,1):
            nx=min(max(s+dx,0),W-1);bits.append((x[...,nx]==0).astype(np.uint8))
    return np.stack(bits,axis=-1)

def entropy_density(x):
    p=x.mean(axis=-1);q=np.clip(p,1e-12,1-1e-12);return -(q*np.log2(q)+(1-q)*np.log2(1-q))

def metric_bundle(arr,neutral):
    div=np.mean(arr!=neutral,axis=-1);shift=shift_divergence(arr,neutral);ex=div==0
    db,tb=context_class(arr);ndb,ntb=context_class(neutral);ctx=(db==ndb)&(tb==ntb)
    fun=np.all(functional_sig(arr)==functional_sig(neutral),axis=-1);out=[]
    for j in range(arr.shape[1]):
        sustain=None
        for t in range(arr.shape[0]):
            if bool(np.all(ex[t:,j])):sustain=t;break
        out.append({"final_exact":bool(ex[-1,j]),"final_shift":bool(shift[-1,j]==0),"final_context":bool(ctx[-1,j]),
                    "final_functional":bool(fun[-1,j]),"mean_divergence":float(div[:,j].mean()),
                    "trajectory_AUD":float(div[:,j].sum()),"time_to_sustained_exact":sustain})
    return out,div,fun

def anticube_probs(div,fun_match,unknown=None):
    d=np.asarray(div,float);u=1-np.asarray(fun_match,float);m=np.zeros_like(d) if unknown is None else np.asarray(unknown,float);known=1-m
    return np.stack([known*(1-d)*(1-u),known*(1-d)*u,known*d*(1-u),known*d*u,m],axis=-1)

def neutral_complexity(neutral):
    ent=entropy_density(neutral).mean(axis=0);uniq=[]
    for j in range(neutral.shape[1]):uniq.append(len({bytes(row.tolist()) for row in neutral[:,j]})/neutral.shape[0])
    return ent,np.asarray(uniq,float)

def horizontal_batch(rule,stratum,reps,severity,collect_temporal=True):
    reps=list(reps);R=len(reps);init=initial_batch(stratum,reps);neutral=evolve(init,rule,T);clean=neutral[:TP+1]
    maps=[];ties=[];ranks=[]
    for j in range(R):
        mp,tie,rank,_=infer_rule(clean[:,j,:].astype(np.int16),rule);maps.append(mp);ties.append(tie);ranks.append(rank)
    width=max(1,int(math.ceil(severity*W)));poisoned=neutral[TP].copy();starts=[]
    for j,rep in enumerate(reps):
        st=seed_int("E1R","HORIZONTAL",stratum,rep,severity)%W;starts.append(st);poisoned[j,window_indices(st,width)]^=1
    poison=np.empty((T-TP+1,R,W),dtype=np.uint8);poison[0]=poisoned
    for k in range(T-TP):poison[k+1]=step_batch(poison[k],rule)
    ia=TA-TP;ant0=poison[ia].copy();sham0=poison[ia].copy();changes=[];rad=TA-TP
    for j,rep in enumerate(reps):
        pred=predicted_row(neutral[TP-1,j],maps[j],TA-(TP-1));cone=cone_indices(starts[j],width,rad)
        center=(starts[j]+(width-1)/2)%W
        def dist(i):
            d=abs(i-center);return min(d,W-d)
        dif=sorted([int(i) for i in cone if ant0[j,i]!=pred[i]],key=lambda i:(dist(i),i));chosen=dif[:width]
        for i in chosen:ant0[j,i]=pred[i]
        changes.append(len(chosen));rng=np.random.default_rng(seed_int("E1R","SHAM",stratum,rep,severity));sh=np.array(cone);rng.shuffle(sh)
        for i in sh[:len(chosen)]:sham0[j,int(i)]^=1
    npost=T-TA;ant=np.empty((npost+1,R,W),dtype=np.uint8);sham=np.empty_like(ant);ant[0]=ant0;sham[0]=sham0
    for k in range(npost):ant[k+1]=step_batch(ant[k],rule);sham[k+1]=step_batch(sham[k],rule)
    pp=poison[ia:];nn=neutral[TA:];pm,pdiv,pfun=metric_bundle(pp,nn);sm,sdiv,sfun=metric_bundle(sham,nn);am,adiv,afun=metric_bundle(ant,nn)
    nent,nuniq=neutral_complexity(nn);rows=[]
    for j,rep in enumerate(reps):
        rows.append({"rule_id":rule,"stratum":stratum,"replicate":rep,"severity":severity,"map_rule_pre_poison":maps[j],
                     "map_rule_tie_size":ties[j],"true_rule_rank":ranks[j],"poison_window_start":starts[j],"poison_width":width,
                     "intervention_changes":changes[j],"neutral_entropy":float(nent[j]),"neutral_unique_fraction":float(nuniq[j]),
                     "poison":pm[j],"sham":sm[j],"antidote":am[j],
                     "antidote_gain_vs_poison":pm[j]["mean_divergence"]-am[j]["mean_divergence"],
                     "antidote_gain_vs_sham":sm[j]["mean_divergence"]-am[j]["mean_divergence"],
                     "antidote_harm":am[j]["mean_divergence"]>pm[j]["mean_divergence"]})
    temporal=[]
    if collect_temporal:
        for label,div,fun in (("POISON",pdiv,pfun),("SHAM",sdiv,sfun),("ANTIDOTE",adiv,afun)):
            probs=anticube_probs(div,fun)
            for ti in range(div.shape[0]):
                avg=probs[ti].mean(axis=0)
                temporal.append({"rule_id":rule,"stratum":stratum,"severity":severity,"condition":label,"time":TA+ti,
                    "mean_divergence":float(div[ti].mean()),"functional_mismatch_rate":float((~fun[ti]).mean()),
                    "anticube_mean":{"SELF_SAFE":float(avg[0]),"SELF_UNSAFE":float(avg[1]),"NONSELF_SAFE":float(avg[2]),
                                     "NONSELF_UNSAFE":float(avg[3]),"UNKNOWN":float(avg[4])}})
    return rows,temporal

def vertical_batch(rule,stratum,reps,severity,operator):
    reps=list(reps);init=initial_batch(stratum,reps);neutral=evolve(init,rule,TA);width=max(1,int(math.ceil(severity*W)));rows=[]
    for j,rep in enumerate(reps):
        true=neutral[:,j,:].astype(np.int16);obs=true.copy();st=seed_int("E1R","VERTICAL",operator,stratum,rep,severity)%W;idx=window_indices(st,width)
        for t in range(TP,TA):
            if operator=="missing":obs[t,idx]=-1
            else:obs[t,idx]=1-obs[t,idx]
        mp,tie,rank,true_score=infer_rule(obs,rule);recon=obs.copy();prev=recon[TP-1].astype(np.uint8)
        for t in range(TP,TA):
            pred=step_mixed(prev[None,:],np.array([mp]))[0].astype(np.int16);cur=recon[t].copy();cur[idx]=pred[idx];recon[t]=cur;prev=cur.astype(np.uint8)
        sham=obs.copy()
        for t in range(TP,TA):
            rng=np.random.default_rng(seed_int("E1R","VERT_SHAM",operator,stratum,rep,severity,t));cur=sham[t].copy();cur[idx]=rng.integers(0,2,size=len(idx));sham[t]=cur
        mask=np.zeros_like(true,dtype=bool);mask[TP:TA,idx]=True;truth=true[mask];raw=obs[mask]
        raw_acc=float(np.mean(raw==truth));ant_acc=float(np.mean(recon[mask]==truth));sham_acc=float(np.mean(sham[mask]==truth))
        ftrue=functional_sig(true[TP:TA].astype(np.uint8));fant=float(np.mean(np.all(functional_sig(recon[TP:TA].astype(np.uint8))==ftrue,axis=-1)))
        fsh=float(np.mean(np.all(functional_sig(sham[TP:TA].astype(np.uint8))==ftrue,axis=-1)));div=1-ant_acc
        p=anticube_probs(np.array([div]),np.array([fant]))[0]
        rows.append({"rule_id":rule,"stratum":stratum,"replicate":rep,"severity":severity,"operator":operator,"window_start":st,"width":width,
            "map_rule":mp,"map_rule_correct":mp==rule,"map_rule_tie_size":tie,"true_rule_rank":rank,"true_rule_score":true_score,
            "raw_observation_accuracy_corrupted_cells":raw_acc,"sham_reconstruction_accuracy":sham_acc,
            "antidote_reconstruction_accuracy":ant_acc,"antidote_gain_vs_sham":ant_acc-sham_acc,
            "sham_functional_match_rate":fsh,"antidote_functional_match_rate":fant,
            "anticube_after_repair":{"SELF_SAFE":float(p[0]),"SELF_UNSAFE":float(p[1]),"NONSELF_SAFE":float(p[2]),"NONSELF_UNSAFE":float(p[3]),"UNKNOWN":float(p[4])},
            "raw_unknown_fraction":float(severity) if operator=="missing" else 0.0})
    return rows

def wilson(k,n,z=1.959963984540054):
    if not n:return [None,None]
    p=k/n;d=1+z*z/n;c=(p+z*z/(2*n))/d;h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [c-h,c+h]

def aggregate_screen(hrows,vrows):
    hg=defaultdict(list);vg=defaultdict(list)
    for r in hrows:hg[(r["rule_id"],r["stratum"],r["severity"])].append(r)
    for r in vrows:vg[(r["rule_id"],r["operator"],r["stratum"],r["severity"])].append(r)
    perf=[]
    for (rule,stratum,sev),rs in sorted(hg.items()):
        def mean(path):
            vals=[]
            for x in rs:
                y=x
                for k in path:y=y[k]
                vals.append(float(y))
            return float(np.mean(vals))
        k=sum(int(x["antidote"]["final_exact"]) for x in rs);n=len(rs)
        perf.append({"context_type":"HORIZONTAL","rule_id":rule,"stratum":stratum,"severity":sev,"n":n,
          "poison_exact_rate":mean(["poison","final_exact"]),"sham_exact_rate":mean(["sham","final_exact"]),
          "antidote_exact_rate":mean(["antidote","final_exact"]),"antidote_exact_wilson95":wilson(k,n),
          "antidote_context_rate":mean(["antidote","final_context"]),"antidote_functional_rate":mean(["antidote","final_functional"]),
          "poison_mean_divergence":mean(["poison","mean_divergence"]),"sham_mean_divergence":mean(["sham","mean_divergence"]),
          "antidote_mean_divergence":mean(["antidote","mean_divergence"]),
          "antidote_gain_vs_poison":float(np.mean([x["antidote_gain_vs_poison"] for x in rs])),
          "antidote_gain_vs_sham":float(np.mean([x["antidote_gain_vs_sham"] for x in rs])),
          "antidote_harm_rate":float(np.mean([x["antidote_harm"] for x in rs])),
          "neutral_entropy":float(np.mean([x["neutral_entropy"] for x in rs])),
          "neutral_unique_fraction":float(np.mean([x["neutral_unique_fraction"] for x in rs])),
          "map_rule_accuracy":float(np.mean([x["map_rule_pre_poison"]==rule for x in rs]))})
    for (rule,op,stratum,sev),rs in sorted(vg.items()):
        perf.append({"context_type":"VERTICAL","rule_id":rule,"operator":op,"stratum":stratum,"severity":sev,"n":len(rs),
          "map_rule_accuracy":float(np.mean([x["map_rule_correct"] for x in rs])),"mean_true_rule_rank":float(np.mean([x["true_rule_rank"] for x in rs])),
          "mean_tie_size":float(np.mean([x["map_rule_tie_size"] for x in rs])),
          "raw_observation_accuracy":float(np.mean([x["raw_observation_accuracy_corrupted_cells"] for x in rs])),
          "sham_reconstruction_accuracy":float(np.mean([x["sham_reconstruction_accuracy"] for x in rs])),
          "antidote_reconstruction_accuracy":float(np.mean([x["antidote_reconstruction_accuracy"] for x in rs])),
          "antidote_gain_vs_sham":float(np.mean([x["antidote_gain_vs_sham"] for x in rs])),
          "antidote_functional_match_rate":float(np.mean([x["antidote_functional_match_rate"] for x in rs]))})
    return perf

def dominates(a,b):
    va=[a["antidote_gain_vs_sham"],a["antidote_exact_rate"],a["antidote_context_rate"],a["antidote_functional_rate"],a["neutral_entropy"],a["neutral_unique_fraction"],-a["antidote_harm_rate"]]
    vb=[b["antidote_gain_vs_sham"],b["antidote_exact_rate"],b["antidote_context_rate"],b["antidote_functional_rate"],b["neutral_entropy"],b["neutral_unique_fraction"],-b["antidote_harm_rate"]]
    return all(x>=y-1e-12 for x,y in zip(va,vb)) and any(x>y+1e-12 for x,y in zip(va,vb))

def pareto_shortlists(perf):
    h=[x for x in perf if x["context_type"]=="HORIZONTAL"];by=defaultdict(list)
    for x in h:by[(x["stratum"],x["severity"])].append(x)
    out={}
    for key,rs in sorted(by.items()):
        front=[a for a in rs if not any(dominates(b,a) for b in rs if b is not a)]
        ranked=sorted(front,key=lambda x:(x["antidote_harm_rate"],-x["antidote_gain_vs_sham"],-x["antidote_exact_rate"],-x["neutral_entropy"],x["rule_id"]))
        out["HORIZONTAL|%s|%.2f"%(key[0],key[1])]={"pareto_rules":[x["rule_id"] for x in sorted(front,key=lambda x:x["rule_id"])],
            "shortlist":[x["rule_id"] for x in ranked[:K_SHORTLIST]],
            "selection_policy":"Pareto first; cap by harm asc, gain desc, exact desc, neutral entropy desc, rule id asc"}
    rg=defaultdict(list)
    for x in h:rg[x["rule_id"]].append(x)
    glob=[]
    for rule,rs in rg.items():
        glob.append({"rule_id":rule,"harm":float(np.mean([x["antidote_harm_rate"] for x in rs])),
            "gain":float(np.mean([x["antidote_gain_vs_sham"] for x in rs])),"exact":float(np.mean([x["antidote_exact_rate"] for x in rs])),
            "entropy":float(np.mean([x["neutral_entropy"] for x in rs]))})
    glob=sorted(glob,key=lambda x:(x["harm"],-x["gain"],-x["exact"],-x["entropy"],x["rule_id"]))
    return out,[x["rule_id"] for x in glob[:K_SHORTLIST]]

def signflip_p(diffs,seed,B=10000):
    d=np.asarray(diffs,float);obs=float(np.mean(d))
    if len(d)==0 or np.allclose(d,0):return 1.0
    rng=np.random.default_rng(seed);count=1
    for _ in range(B):
        s=rng.choice(np.array([-1.0,1.0]),size=len(d))
        if abs(float(np.mean(d*s)))>=abs(obs)-1e-15:count+=1
    return count/(B+1)

def holm(ps):
    m=len(ps);order=sorted(range(m),key=lambda i:ps[i]);adj=[0.0]*m;prev=0.0
    for rank,i in enumerate(order):
        val=min(1.0,(m-rank)*ps[i]);prev=max(prev,val);adj[i]=prev
    return adj

def run_confirmatory(shortlists,global_shortlist):
    global_rule=int(global_shortlist[0]);records=[];contexts=[]
    for ck in sorted(shortlists):
        _,stratum,sevs=ck.split("|");sev=float(sevs);selected=int(shortlists[ck]["shortlist"][0]);randrule=random.Random(seed_int("E1R","CONFIRM_RANDOM_RULE",ck)).randrange(256)
        arms={}
        for label,rule in (("CONTEXT_SELECTED_RULE",selected),("BEST_GLOBAL_TRAIN_RULE",global_rule),("RANDOM_RULE",randrule)):
            rr,_=horizontal_batch(rule,stratum,CONFIRM_REPS,sev,False);arms[label]=rr
            for x in rr:records.append({"context":ck,"arm":label,"candidate_rule":rule,"replicate":x["replicate"],
                "antidote_gain_vs_sham":x["antidote_gain_vs_sham"],"antidote_mean_divergence":x["antidote"]["mean_divergence"],
                "antidote_exact":x["antidote"]["final_exact"],"neutral_entropy":x["neutral_entropy"]})
        dif=[a["antidote_gain_vs_sham"]-b["antidote_gain_vs_sham"] for a,b in zip(arms["CONTEXT_SELECTED_RULE"],arms["BEST_GLOBAL_TRAIN_RULE"])]
        contexts.append({"context":ck,"selected_rule":selected,"global_rule":global_rule,"random_rule":randrule,"n":len(dif),
            "mean_gain_difference_selected_minus_global":float(np.mean(dif)),"median_gain_difference":float(np.median(dif)),
            "p_unadjusted":signflip_p(dif,seed_int("E1R","CONFIRM_P",ck))})
    adj=holm([x["p_unadjusted"] for x in contexts])
    for x,a in zip(contexts,adj):
        x["p_holm"]=a;x["state"]="SUPPORTED" if a<.05 and x["mean_gain_difference_selected_minus_global"]>0 else ("NEGATIVE" if a<.05 else "FAIL_TO_REJECT_H0")
    alld=[]
    for x in contexts:
        ck=x["context"]
        if x["selected_rule"]==global_rule:alld.extend([0.0]*len(CONFIRM_REPS))
        else:
            s=[z for z in records if z["context"]==ck and z["arm"]=="CONTEXT_SELECTED_RULE"];g=[z for z in records if z["context"]==ck and z["arm"]=="BEST_GLOBAL_TRAIN_RULE"]
            alld.extend([a["antidote_gain_vs_sham"]-b["antidote_gain_vs_sham"] for a,b in zip(s,g)])
    p=signflip_p(alld,2026092801)
    overall={"global_rule":global_rule,"paired_n":len(alld),"mean_difference":float(np.mean(alld)),"median_difference":float(np.median(alld)),
        "p_signflip":p,"contexts_positive":sum(x["mean_gain_difference_selected_minus_global"]>0 for x in contexts),"contexts_total":len(contexts)}
    overall["state"]="SUPPORTED" if p<.05 and overall["mean_difference"]>0 else ("NEGATIVE" if p<.05 else "FAIL_TO_REJECT_H0")
    return records,contexts,overall

def compose(row,r1,r2,k=4):
    x=row[None,:].copy()
    for _ in range(k):x=step_batch(x,r1)
    for _ in range(k):x=step_batch(x,r2)
    return x[0]

def run_composition(shortlists):
    rows=[];summary=[]
    for ck in sorted(shortlists):
        _,stratum,sevs=ck.split("|");sev=float(sevs);rules=shortlists[ck]["shortlist"][:K_COMPOSITION];per=defaultdict(list)
        for rep in COMPOSITION_REPS:
            init=initial_batch(stratum,[rep])[0];width=max(1,int(math.ceil(sev*W)));st=seed_int("E1R","COMPOSE_POISON",stratum,rep,sev)%W
            poisoned=init.copy();poisoned[window_indices(st,width)]^=1
            for r1 in rules:
                for r2 in rules:
                    clean=compose(init,r1,r2);bad=compose(poisoned,r1,r2);revclean=compose(init,r2,r1);revbad=compose(poisoned,r2,r1)
                    d=float(np.mean(clean!=bad));dr=float(np.mean(revclean!=revbad));same=bool(np.array_equal(clean,revclean) and np.array_equal(bad,revbad))
                    rec={"context":ck,"replicate":rep,"rule_1":r1,"rule_2":r2,"final_divergence":d,"reverse_final_divergence":dr,
                         "order_abs_effect":abs(d-dr),"order_outputs_identical":same};rows.append(rec);per[(r1,r2)].append(rec)
        for (r1,r2),rs in sorted(per.items()):
            summary.append({"context":ck,"rule_1":r1,"rule_2":r2,"n":len(rs),"mean_final_divergence":float(np.mean([x["final_divergence"] for x in rs])),
                "mean_order_abs_effect":float(np.mean([x["order_abs_effect"] for x in rs])),"noncommutative_fraction":float(np.mean([not x["order_outputs_identical"] for x in rs]))})
    return rows,summary

def build_figures(perf,shortlists,confirm,comp,temporal):
    out=ROOT/"figures/e1r";out.mkdir(parents=True,exist_ok=True)
    try:import matplotlib.pyplot as plt
    except Exception as e:return {"state":"NOT_BUILT_MATPLOTLIB_UNAVAILABLE","error":repr(e),"files":[]}
    files=[];h=[x for x in perf if x["context_type"]=="HORIZONTAL"];ctxs=sorted({(x["stratum"],x["severity"]) for x in h});cm={c:i for i,c in enumerate(ctxs)}
    mat=np.full((256,len(ctxs)),np.nan)
    for x in h:mat[x["rule_id"],cm[(x["stratum"],x["severity"])]]=x["antidote_gain_vs_sham"]
    fig,ax=plt.subplots(figsize=(10,8));im=ax.imshow(mat,aspect="auto",interpolation="nearest");ax.set_xlabel("context");ax.set_ylabel("ECA rule")
    ax.set_xticks(range(len(ctxs)));ax.set_xticklabels(["%s\n%.2f"%c for c in ctxs],rotation=45,ha="right");ax.set_title("E1R all-256: antidote gain vs sham");fig.colorbar(im,ax=ax,label="mean divergence reduction")
    p=out/"F-E1R-1_all256_context_heatmap.png";fig.tight_layout();fig.savefig(p,dpi=160);plt.close(fig);files.append(str(p.relative_to(ROOT)))
    v=[x for x in perf if x["context_type"]=="VERTICAL"];fig,ax=plt.subplots(figsize=(7,4));ax.bar(["horizontal-state","vertical-history"],[float(np.mean([x["antidote_gain_vs_sham"] for x in h])),float(np.mean([x["antidote_gain_vs_sham"] for x in v]))]);ax.set_title("Distinct corruption endpoints")
    p=out/"F-E1R-2_horizontal_vertical.png";fig.tight_layout();fig.savefig(p,dpi=160);plt.close(fig);files.append(str(p.relative_to(ROOT)))
    fig,ax=plt.subplots(figsize=(7,4));ax.bar(["Exact","Contextual","Functional"],[float(np.mean([x["antidote_exact_rate"] for x in h])),float(np.mean([x["antidote_context_rate"] for x in h])),float(np.mean([x["antidote_functional_rate"] for x in h]))]);ax.set_ylim(0,1);ax.set_title("Distinct restoration criteria")
    p=out/"F-E1R-4_restoration_types.png";fig.tight_layout();fig.savefig(p,dpi=160);plt.close(fig);files.append(str(p.relative_to(ROOT)))
    sample=[x for x in h if x["stratum"]=="balanced" and abs(x["severity"]-.10)<1e-9];fig,ax=plt.subplots(figsize=(7,5));ax.scatter([x["neutral_entropy"] for x in sample],[x["antidote_gain_vs_sham"] for x in sample],s=10);pr=set(shortlists["HORIZONTAL|balanced|0.10"]["pareto_rules"])
    for x in sample:
        if x["rule_id"] in pr:ax.annotate(str(x["rule_id"]),(x["neutral_entropy"],x["antidote_gain_vs_sham"]),fontsize=6)
    ax.set_xlabel("neutral temporal bit entropy");ax.set_ylabel("antidote gain vs sham");ax.set_title("Pareto candidates")
    p=out/"F-E1R-5_pareto.png";fig.tight_layout();fig.savefig(p,dpi=160);plt.close(fig);files.append(str(p.relative_to(ROOT)))
    fig,ax=plt.subplots(figsize=(10,4));ax.bar(range(len(confirm)),[x["mean_gain_difference_selected_minus_global"] for x in confirm]);ax.axhline(0,linewidth=1);ax.set_xticks(range(len(confirm)));ax.set_xticklabels([x["context"].replace("HORIZONTAL|","") for x in confirm],rotation=60,ha="right",fontsize=7);ax.set_title("Fresh-replicate context selection")
    p=out/"F-E1R-6_context_selected.png";fig.tight_layout();fig.savefig(p,dpi=160);plt.close(fig);files.append(str(p.relative_to(ROOT)))
    fig,ax=plt.subplots(figsize=(7,4));ax.hist([x["mean_order_abs_effect"] for x in comp],bins=30);ax.set_xlabel("order absolute effect");ax.set_title("Ordered rule-pair asymmetry")
    p=out/"F-E1R-7_order_asymmetry.png";fig.tight_layout();fig.savefig(p,dpi=160);plt.close(fig);files.append(str(p.relative_to(ROOT)))
    by=defaultdict(list)
    for x in temporal:by[(x["condition"],x["time"])].append(x["anticube_mean"])
    fig,ax=plt.subplots(figsize=(8,5))
    for cond in ("POISON","SHAM","ANTIDOTE"):
        ts=sorted(t for c,t in by if c==cond);ys=[np.mean([z["SELF_SAFE"] for z in by[(cond,t)]]) for t in ts];ax.plot(ts,ys,label=cond)
    ax.set_xlabel("time");ax.set_ylabel("mean P(SELF_SAFE)");ax.set_title("Public simulation Anticube");ax.legend()
    p=out/"F-E1R-8_anticube_temporal.png";fig.tight_layout();fig.savefig(p,dpi=160);plt.close(fig);files.append(str(p.relative_to(ROOT)))
    return {"state":"BUILT","files":files}

def csv_file(path,rows):
    p=ROOT/path;p.parent.mkdir(parents=True,exist_ok=True)
    if not rows:p.write_text("");return
    keys=sorted(set().union(*(r.keys() for r in rows)))
    with p.open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=keys);w.writeheader()
        for r in rows:w.writerow({k:(json.dumps(v,sort_keys=True) if isinstance(v,(dict,list)) else v) for k,v in r.items()})

def scan_vcc():
    cand=[];active=Path("/Users/byron/projects/active")
    for p in active.iterdir():
        if not p.is_dir() or not any(k in p.name.lower() for k in ("cloudmer","genesis","vcc")):continue
        q=run(["git","-C",str(p),"rev-parse","--git-dir"],check=False,capture=True,cwd=active)
        if q.returncode:continue
        def g(*args):
            z=run(["git","-C",str(p),*args],check=False,capture=True,cwd=active);return z.stdout.strip() if z.returncode==0 else None
        cand.append({"path":str(p),"branch":g("rev-parse","--abbrev-ref","HEAD"),"head":g("rev-parse","HEAD"),"origin":g("remote","get-url","origin"),"status":g("status","--porcelain")})
    state="DEFERRED_PENDING_EXACT_VCC_STATE_RECOVERY"
    if len(cand)==1 and cand[0].get("head") and cand[0].get("status")=="":state="RECOVERED_LOCAL_REPO_NOT_EXECUTED"
    return {"schema":"E1R_VCC_TRANSLATION_REGISTRY_V1","state":state,"evidence_level":"SIMULATED_COMPUTATIONAL_TRANSFORM_OF_BIOLOGICAL_DATA","candidates":cand,
      "biological_mechanism_claim":False,"arms":[{"arm":"V0_RAW","state":"PREREG_ONLY"},{"arm":"V1_FIXED_ECA","state":"PREREG_ONLY"},{"arm":"V2_CONTEXT_SELECTED_ECA","state":"PREREG_ONLY"},{"arm":"V3_RULE_COMPOSITION","state":"PREREG_ONLY"},{"arm":"V4_ECA_PLUS_ANTICUBE","state":"PREREG_ONLY"},{"arm":"V5_ECA_PLUS_ANTICUBE_PLUS_DELTAGSTAR","state":"NOT_TESTED_DELTAGSTAR_NOT_COMPUTED"},{"arm":"V6_FULL_VITA01","state":"PREREG_ONLY"}]}

def main():
    os.chdir(ROOT);status("RECOVER","RUNNING")
    if (ROOT/".venv").exists():shutil.rmtree(ROOT/".venv",ignore_errors=True)
    if not SHARED_PY.exists():raise RuntimeError("shared Python environment unavailable")
    run(["git","fetch","origin","--prune"])
    if run(["git","rev-parse","HEAD"],capture=True).stdout.strip()!=PARENT_COMMIT:raise RuntimeError("branch parent mismatch")
    git_clean_except(["scripts/e1r_daisy_execute.py"])
    disk=shutil.disk_usage(ROOT)
    if disk.free<250*1024*1024:raise RuntimeError("insufficient free disk: "+str(disk.free))
    pv=verify_parent_metadata();env={**os.environ,"PYTHONPATH":str(ROOT),"PYTHONDONTWRITEBYTECODE":"1"}
    run([str(SHARED_PY),"-m","pytest","-q"],env=env);run([str(SHARED_PY),"scripts/secret_scan.py"],env=env)
    status("RECOVER","PASS",parent_verify=pv,free_bytes=disk.free)

    prior={"schema":"E1R_PRIOR_ART_REGISTRY_V1","retrieval_date":"2026-09-28","novelty_state":"NOVELTY_CANDIDATE","sources":[
      {"id":"Ather_Gordon_2026","title":"Ruliological resilience: Pattern restoration and robustness in Wolfram patterns. A basis for regeneration, not just in Cone Shells?","venue":"BioSystems 267 (2026) 105869","doi":"10.1016/j.biosystems.2026.105869","supported_scope":"all 256 ECA rules; localized perturbations; Hamming/XOR restoration; 100 trials per rule","implication":"all-256 perturbation/restoration is prior art"},
      {"id":"Elser_2021","title":"Reconstructing cellular automata rules from observations at nonconsecutive times","venue":"Physical Review E 104, 034301","doi":"10.1103/PhysRevE.104.034301","supported_scope":"CA rule and hidden-state reconstruction from nonconsecutive observations","implication":"rule reconstruction from incomplete temporal observations is prior art"},
      {"id":"Bagnoli_Rechtman_Ruffo_1998","title":"Lyapunov Exponents versus Expansivity and Sensitivity in Cellular Automata","venue":"Journal of Complexity 14(2):210-233","doi":"10.1006/jcom.1998.0474","supported_scope":"sensitivity and perturbation propagation in cellular automata","implication":"perturbation propagation is prior art"},
      {"id":"Vithia_E1_predecessor","type":"internal_governed","breakpoint":"UFA-JEV-BP-0015","supported_scope":"all 256 ECA rules under observation corruption for rule identification, not restoration"}],
      "candidate_gap":"typed integration of exact evidence identity, world-state vs observation-history corruption, intrinsic vs intervention-induced vs contextual vs functional restoration, Anticube successor state, bounded model interfaces, and append-only custody",
      "claim_ceiling":"NOVELTY_CANDIDATE only"}
    write_json("evidence/e1r/PRIOR_ART_REGISTRY.json",prior)
    write_text("docs/prereg/E1R_PRIOR_ART.md","# E1R prior-art freeze\n\nAll-256 ECA restoration, CA rule reconstruction, perturbation propagation, Merkle commitments, and knowledge graphs are not individually claimed novel. The candidate contribution is the typed integration recorded in evidence/e1r/PRIOR_ART_REGISTRY.json. Novelty remains NOVELTY_CANDIDATE.\n")
    bp29=make_bp("e1r-prior-art","LITERATURE_AND_PRIOR_ART_FROZEN",[atom_record("evidence/e1r/PRIOR_ART_REGISTRY.json","PriorArtRegistryFCO","prior_art"),atom_record("docs/prereg/E1R_PRIOR_ART.md","PreregistrationFCO","prior_art"),atom_record("scripts/e1r_daisy_execute.py","CodeFCO","code")],{"stage":"E1R_PRIOR_ART_FREEZE","novelty_state":"NOVELTY_CANDIDATE"},"e1r: freeze prior art and execution source",["evidence/e1r","docs/prereg/E1R_PRIOR_ART.md","scripts/e1r_daisy_execute.py"])

    model={"schema":"E1R_OBJECT_MODEL_V1","objects":{"RuleFCO":["rule_id","wolfram_rule_number","truth_table","canonical_rule_bytes_hex","rule_hash","kernel_version"],"RuleApplicationFCO":["rule_fco_ref","input_state_ref","context_ref","time","orientation","perturbation_condition","seed","output_state_ref"],"TrajectoryFCO":["trajectory_id","rule_refs","state_refs"],"PerturbationFCO":["condition","orientation","severity","window","seed"],"InterventionFCO":["policy","budget","source_context_refs","changed_indices"],"RestorationClassificationFCO":["R_EXACT","R_SHIFT","R_CONTEXT","R_FUNCTIONAL","R_TRAJECTORY"],"DistributionFCO":["distribution_type","support","probabilities","evidence_refs"]},"edges":["DERIVED_FROM","EXECUTED_WITH","PERTURBED_BY","OBSERVED_AS","CONTEXTUALIZED_BY","COMPARED_WITH","INTERVENED_BY","RESTORED_UNDER","EQUIVALENT_UNDER","CONTRADICTED_BY","EVIDENCE_FOR","REPLAY_OF","SUPERSEDES"],"edge_semantics":"declared relationship, not causality"}
    write_json("schemas/e1r/E1R_OBJECT_MODEL_V1.json",model);rules=[];ksha=sha_file(ROOT/"src/kernels/eca.py")
    for r in range(256):
        tt=[(r>>i)&1 for i in range(8)];canon={"schema":"E1R_RULE_CANON_V1","wolfram_rule_number":r,"neighborhood_index":"4*l+2*c+r","truth_table_lsb_first":tt,"boundary":"periodic","kernel_sha256":ksha}
        rules.append({"schema":"RuleFCO_V1","rule_id":"ECA_RULE_%03d"%r,"wolfram_rule_number":r,"truth_table":tt,"canonical_rule_bytes_hex":cbytes(canon).hex(),"rule_hash":cid(canon),"kernel_version":ksha,"source_reference":"Wolfram ECA numbering","implementation_reference":"src/kernels/eca.py","wolfram_class":"UNKNOWN_NOT_INGESTED"})
    write_jsonl("data/e1r/E1R_RULE_FCO_REGISTRY_V1/rules.jsonl",rules);rm=make_manifest("E1R_RULE_FCO_REGISTRY_V1",["data/e1r/E1R_RULE_FCO_REGISTRY_V1/rules.jsonl"],{"rules":256,"boundary":"periodic"},"identity only")
    write_json("data/e1r/E1R_RULE_FCO_REGISTRY_V1/MANIFEST.json",rm);write_json("RULE_FCO_REGISTRY.json",{"dataset_id":"E1R_RULE_FCO_REGISTRY_V1","fmo_root":rm["fmo_root"],"rules":256})
    bp30=make_bp("e1r-rule-fcos","ONTOLOGY_AND_RULE_FCO_FROZEN",[atom_record("schemas/e1r/E1R_OBJECT_MODEL_V1.json","SchemaFCO","ontology"),atom_record("data/e1r/E1R_RULE_FCO_REGISTRY_V1/rules.jsonl","RuleFCORegistry","rules"),atom_record("data/e1r/E1R_RULE_FCO_REGISTRY_V1/MANIFEST.json","DatasetManifestFCO","rules"),atom_record("RULE_FCO_REGISTRY.json","RegistryFCO","rules")],{"stage":"E1R_ONTOLOGY_RULE_FREEZE","rules":256,"rule_registry_root":rm["fmo_root"]},"e1r: freeze object model and all 256 RuleFCOs",["schemas/e1r","data/e1r/E1R_RULE_FCO_REGISTRY_V1","RULE_FCO_REGISTRY.json"])

    defs={"schema":"E1R_RESTORATION_DEFINITIONS_V1","world":{"W":W,"T":T,"boundary":"periodic","t_poison":TP,"t_antidote":TA},"R_EXACT":"bitwise equality","R_SHIFT":{"shifts":list(SHIFTS)},"R_CONTEXT":"same 5-percent density and transition bins","R_FUNCTIONAL":"same CA-dodge safe-action signature at three fixed observers","R_TRAJECTORY":"normalized Hamming divergence and AUD","invariant":"INTRINSIC_RECOVERY != INTERVENTION_RECOVERY != CONTEXTUAL_EQUIVALENCE != FUNCTIONAL_RECOVERY"}
    anti={"schema":"PUBLIC_SIMULATION_ANTICUBE_E1R_V1","states":["SELF_SAFE","SELF_UNSAFE","NONSELF_SAFE","NONSELF_UNSAFE","UNKNOWN"],"mapping":{"SELF_SAFE":"(1-m)(1-d)(1-u)","SELF_UNSAFE":"(1-m)(1-d)u","NONSELF_SAFE":"(1-m)d(1-u)","NONSELF_UNSAFE":"(1-m)du","UNKNOWN":"m"},"claim_ceiling":"simulation evaluation distribution only; not biological and not independently calibrated"}
    write_json("schemas/e1r/E1R_RESTORATION_DEFINITIONS_V1.json",defs);write_json("schemas/e1r/PUBLIC_SIMULATION_ANTICUBE_E1R_V1.json",anti)
    bp31=make_bp("e1r-restoration-definitions","PERTURBATION_AND_RESTORATION_DEFINITIONS_FROZEN",[atom_record("schemas/e1r/E1R_RESTORATION_DEFINITIONS_V1.json","SchemaFCO","definitions"),atom_record("schemas/e1r/PUBLIC_SIMULATION_ANTICUBE_E1R_V1.json","SchemaFCO","definitions")],{"stage":"E1R_RESTORATION_DEFINITION_FREEZE","delta_g_star":"NOT_COMPUTED"},"e1r: freeze restoration and Anticube definitions",["schemas/e1r"])

    rand={"schema":"E1R_RANDOMIZATION_V1","seed":"first 64 bits SHA256 of pipe-delimited experiment fields, masked to 31 bits","clock_randomness":False,"paired_across_rules":True,"initial_state_seed_excludes_rule_id":True,"perturbation_seed_excludes_rule_id":True,"pilot_replicates":list(PILOT_REPS),"confirmatory_replicates":list(CONFIRM_REPS),"composition_replicates":list(COMPOSITION_REPS)}
    cfg={"schema":"E1R_SCREEN_CONFIG_V1","all_rules":True,"W":W,"T":T,"t_poison":TP,"t_antidote":TA,"strata":list(STRATA),"severities":list(SEVERITIES),"vertical_operators":list(VERT_OPS),"pilot_replicates":20,"conditions":["N0_NEUTRAL","P1_HORIZONTAL_STATE_POISON","P2_VERTICAL_HISTORY_POISON","S1_SHAM","A1_CONTEXTUAL_ANTIDOTE"],"screening":"descriptive/Pareto; no per-rule discovery p-values","selection":"Pareto then fixed lexicographic shortlist; fresh replicate confirmation"}
    stats={"schema":"E1R_STATS_PLAN_V1","restoration_rate":"Wilson 95% CI","screen":"no 256 uncorrected discovery p-values","confirmatory_rule_selection":{"test":"paired sign-flip permutation 10000 draws","multiplicity":"Holm over 12 contexts","support":"Holm/overall p<0.05 and positive mean"},"composition":"screening only"}
    write_json("schemas/e1r/E1R_RANDOMIZATION_V1.json",rand);write_json("schemas/e1r/E1R_SCREEN_CONFIG_V1.json",cfg);write_json("schemas/e1r/E1R_STATS_PLAN_V1.json",stats)
    bp32=make_bp("e1r-randomization","RANDOMIZATION_AND_DATASET_PROTOCOL_FROZEN",[atom_record("schemas/e1r/E1R_RANDOMIZATION_V1.json","SchemaFCO","randomization"),atom_record("schemas/e1r/E1R_SCREEN_CONFIG_V1.json","SchemaFCO","randomization"),atom_record("schemas/e1r/E1R_STATS_PLAN_V1.json","SchemaFCO","randomization")],{"stage":"E1R_RANDOMIZATION_FREEZE","future_state_leakage":"FORBIDDEN","paired_inputs_across_rules":True},"e1r: freeze randomization and statistics",["schemas/e1r"])

    prereg="# E1R all-256 restoration screen\n\nAll 256 rules are screened with paired initial states and perturbations. Horizontal corruption changes world state; vertical corruption changes observation/history only. Neutral, poison, sham and contextual antidote remain distinct. Restoration is recorded separately as exact, shift, contextual, functional and trajectory convergence. Pilot is screening only. Context rule selection uses fresh replicate IDs. DeltaGStar is NOT_COMPUTED unless the actual governed private implementation becomes available. VCC execution is separate and cannot imply biological mechanism.\n"
    write_text("docs/prereg/E1R_RULE_CONTEXT_RESTORATION.md",prereg)
    bp33=make_bp("e1r-all256-prereg","ALL_256_SINGLE_RULE_PREREGISTERED",[atom_record("docs/prereg/E1R_RULE_CONTEXT_RESTORATION.md","PreregistrationFCO","prereg"),atom_record("schemas/e1r/E1R_SCREEN_CONFIG_V1.json","SchemaFCO","prereg"),atom_record("schemas/e1r/E1R_STATS_PLAN_V1.json","SchemaFCO","prereg"),atom_record("scripts/e1r_daisy_execute.py","CodeFCO","code")],{"stage":"E1R_ALL256_PREREG","rules":256,"pilot_replicates":20,"model_calls":0,"delta_g_star":"NOT_COMPUTED"},"e1r: preregister all-256 restoration screen",["docs/prereg/E1R_RULE_CONTEXT_RESTORATION.md"])

    status("SCREEN_ALL_256_RULES","RUNNING");hrows=[];vrows=[];temporal=[];t0=time.time()
    for rule in range(256):
        for stratum in STRATA:
            for sev in SEVERITIES:
                rr,tt=horizontal_batch(rule,stratum,PILOT_REPS,sev,True);hrows.extend(rr);temporal.extend(tt)
                for op in VERT_OPS:vrows.extend(vertical_batch(rule,stratum,PILOT_REPS,sev,op))
        if rule%32==0:status("SCREEN_ALL_256_RULES","RUNNING",rule_completed=rule,elapsed_s=round(time.time()-t0,1))
    perf=aggregate_screen(hrows,vrows);shortlists,global_shortlist=pareto_shortlists(perf);ds="E1R_ALL256_SCREEN_PILOT_V1";base="data/e1r/"+ds
    write_jsonl_gz(base+"/horizontal_rows.jsonl.gz",hrows);write_jsonl_gz(base+"/vertical_rows.jsonl.gz",vrows);write_jsonl_gz(base+"/anticube_temporal_aggregate.jsonl.gz",temporal);write_jsonl(base+"/rule_context_performance.jsonl",perf)
    write_json(base+"/PARETO_RULE_SETS.json",{"schema":"E1R_PARETO_RULE_SETS_V1","contexts":shortlists,"global_shortlist":global_shortlist})
    screen={"schema":"E1R_ALL256_SCREEN_SUMMARY_V1","rules":256,"horizontal_case_rows":len(hrows),"vertical_case_rows":len(vrows),"total_case_rows":len(hrows)+len(vrows),"neutral_base_contexts":256*len(STRATA)*len(PILOT_REPS),"elapsed_seconds":round(time.time()-t0,3),"global_shortlist":global_shortlist,"delta_g_star":"NOT_COMPUTED","model_calls":0,"classification":"SCREENING_EXPLORATORY"}
    write_json(base+"/SCREEN_SUMMARY.json",screen);mf=make_manifest(ds,[base+"/horizontal_rows.jsonl.gz",base+"/vertical_rows.jsonl.gz",base+"/anticube_temporal_aggregate.jsonl.gz",base+"/rule_context_performance.jsonl",base+"/PARETO_RULE_SETS.json",base+"/SCREEN_SUMMARY.json"],cfg,"screening evidence; no universal best rule claim");write_json(base+"/MANIFEST.json",mf)
    write_json("RULE_CONTEXT_REGISTRY.json",{"schema":"RULE_CONTEXT_REGISTRY_V1","dataset_id":ds,"dataset_root":mf["fmo_root"],"contexts":shortlists,"global_shortlist":global_shortlist});write_json("RESTORATION_RESULT_REGISTRY.json",{"schema":"RESTORATION_RESULT_REGISTRY_V1","dataset_id":ds,"dataset_root":mf["fmo_root"],"definitions":"schemas/e1r/E1R_RESTORATION_DEFINITIONS_V1.json","screen_summary":screen})
    bp34=make_bp("e1r-all256-result","ALL_256_SINGLE_RULE_SCREEN_COMPLETE",[atom_record(base+"/MANIFEST.json","DatasetManifestFCO","dataset"),atom_record(base+"/SCREEN_SUMMARY.json","ResultSummaryFCO","result"),atom_record(base+"/PARETO_RULE_SETS.json","DerivedEvidenceFCO","result"),atom_record(base+"/rule_context_performance.jsonl","DerivedEvidenceFCO","result"),atom_record("RULE_CONTEXT_REGISTRY.json","RegistryFCO","result"),atom_record("RESTORATION_RESULT_REGISTRY.json","RegistryFCO","result")],{"stage":"E1R_ALL256_RESULT","dataset_id":ds,"dataset_root":mf["fmo_root"],"total_case_rows":len(hrows)+len(vrows),"classification":"SCREENING_EXPLORATORY","model_calls":0,"delta_g_star":"NOT_COMPUTED"},"e1r: complete all-256 restoration screen",[base,"RULE_CONTEXT_REGISTRY.json","RESTORATION_RESULT_REGISTRY.json"])

    plan={"schema":"E1R_RULE_SELECTION_CONFIRMATORY_V1","source_screen_breakpoint":bp34["bp_id"],"fresh_replicates":list(CONFIRM_REPS),"contexts":shortlists,"global_shortlist":global_shortlist,"arms":["CONTEXT_SELECTED_RULE","BEST_GLOBAL_TRAIN_RULE","RANDOM_RULE"],"primary_metric":"antidote_gain_vs_sham mean divergence","primary_test":"paired sign-flip permutation 10000 draws; Holm over 12 contexts","pilot_reuse":"selection only"}
    write_json("docs/prereg/E1R_RULE_SELECTION_CONFIRMATORY.json",plan)
    bp35=make_bp("e1r-rule-selection-prereg","RULE_SELECTION_CONFIRMATORY_PREREGISTERED",[atom_record("docs/prereg/E1R_RULE_SELECTION_CONFIRMATORY.json","PreregistrationFCO","prereg"),atom_record(base+"/PARETO_RULE_SETS.json","ScreeningEvidenceFCO","screening"),atom_record("RULE_CONTEXT_REGISTRY.json","RegistryFCO","screening")],{"stage":"E1R_RULE_SELECTION_PREREG","fresh_replicates":len(CONFIRM_REPS),"selection_from_test_set":False},"e1r: preregister context rule selection",["docs/prereg/E1R_RULE_SELECTION_CONFIRMATORY.json"])
    status("SELECT_CONTEXTUAL_SIGNAL","RUNNING");confrows,confctx,confover=run_confirmatory(shortlists,global_shortlist);cbase="data/e1r/E1R_RULE_SELECTION_CONFIRMATORY_V1"
    write_jsonl_gz(cbase+"/rows.jsonl.gz",confrows);write_json(cbase+"/CONTEXT_RESULTS.json",confctx);write_json(cbase+"/RESULT.json",confover);cmf=make_manifest("E1R_RULE_SELECTION_CONFIRMATORY_V1",[cbase+"/rows.jsonl.gz",cbase+"/CONTEXT_RESULTS.json",cbase+"/RESULT.json"],plan,"fresh replicate context-selected vs global/random comparison");write_json(cbase+"/MANIFEST.json",cmf)
    bp36=make_bp("e1r-rule-selection-result","RULE_SELECTION_CONFIRMATORY_COMPLETE",[atom_record(cbase+"/MANIFEST.json","DatasetManifestFCO","dataset"),atom_record(cbase+"/RESULT.json","ClaimDecisionFCO","result"),atom_record(cbase+"/CONTEXT_RESULTS.json","DerivedEvidenceFCO","result")],{"stage":"E1R_RULE_SELECTION_RESULT","dataset_root":cmf["fmo_root"],"claim_state":confover["state"],"model_calls":0},"e1r: complete context rule selection",[cbase])

    compplan={"schema":"E1R_RULE_COMPOSITION_SCREEN_V1","source_selection_breakpoint":bp36["bp_id"],"candidate_policy":"top 4 per context","ordered_pairs":"all 4x4","fresh_replicates":list(COMPOSITION_REPS),"steps_per_rule":4,"classification":"SCREENING_EXPLORATORY"}
    write_json("docs/prereg/E1R_RULE_COMPOSITION.json",compplan);bp37=make_bp("e1r-rule-composition-prereg","RULE_COMPOSITION_SCREEN_PREREGISTERED",[atom_record("docs/prereg/E1R_RULE_COMPOSITION.json","PreregistrationFCO","prereg"),atom_record("RULE_CONTEXT_REGISTRY.json","RegistryFCO","source")],{"stage":"E1R_RULE_COMPOSITION_PREREG","top_k":K_COMPOSITION},"e1r: preregister rule composition",["docs/prereg/E1R_RULE_COMPOSITION.json"])
    status("TEST_ORDER_CROSSES","RUNNING");comprows,compsum=run_composition(shortlists);obase="data/e1r/E1R_RULE_COMPOSITION_SCREEN_V1";write_jsonl_gz(obase+"/rows.jsonl.gz",comprows);write_jsonl(obase+"/pair_context_summary.jsonl",compsum)
    osum={"schema":"E1R_RULE_COMPOSITION_SUMMARY_V1","rows":len(comprows),"mean_order_abs_effect":float(np.mean([x["mean_order_abs_effect"] for x in compsum])),"cells_with_noncommutativity":sum(x["noncommutative_fraction"]>0 for x in compsum),"context_pair_cells":len(compsum)};write_json(obase+"/SUMMARY.json",osum);omf=make_manifest("E1R_RULE_COMPOSITION_SCREEN_V1",[obase+"/rows.jsonl.gz",obase+"/pair_context_summary.jsonl",obase+"/SUMMARY.json"],compplan,"screening order-composition evidence");write_json(obase+"/MANIFEST.json",omf)
    bp38=make_bp("e1r-rule-composition-result","RULE_COMPOSITION_SCREEN_COMPLETE",[atom_record(obase+"/MANIFEST.json","DatasetManifestFCO","dataset"),atom_record(obase+"/SUMMARY.json","ResultSummaryFCO","result"),atom_record(obase+"/pair_context_summary.jsonl","DerivedEvidenceFCO","result")],{"stage":"E1R_RULE_COMPOSITION_RESULT","dataset_root":omf["fmo_root"],"classification":"SCREENING_EXPLORATORY"},"e1r: complete ordered rule composition",[obase])

    orders=[{"id":"O_ECA_THEN_ANTICUBE","state":"EXECUTED_IN_E1R_SCREEN","type_valid":True},{"id":"O_ANTICUBE_THEN_ECA","state":"ABSTAIN_TYPE_ERROR","type_valid":False,"reason":"no frozen projection from five-state distribution to binary lattice"},{"id":"O_ECA_THEN_DELTAGSTAR_THEN_ANTICUBE","state":"NOT_TESTED_DELTAGSTAR_NOT_COMPUTED","type_valid":None},{"id":"O_RAW_CONTEXT","state":"VALID_CONTROL","type_valid":True}]
    write_json("TRANSFORM_ORDER_REGISTRY.json",{"schema":"TRANSFORM_ORDER_REGISTRY_V1","orders":orders,"commutativity_claim":"not assumed; rule-pair order screened separately"})
    bp39=make_bp("e1r-transform-order-prereg","TRANSFORM_ORDER_TYPE_PROTOCOL_FROZEN",[atom_record("TRANSFORM_ORDER_REGISTRY.json","TransformOrderRegistryFCO","order")],{"stage":"E1R_TRANSFORM_ORDER_PREREG","delta_g_star":"NOT_COMPUTED"},"e1r: freeze transform-order protocol",["TRANSFORM_ORDER_REGISTRY.json"])
    write_json("evidence/e1r/TRANSFORM_ORDER_RESULT.json",{"schema":"E1R_TRANSFORM_ORDER_RESULT_V1","orders":orders,"ordered_rule_pair_dataset":"E1R_RULE_COMPOSITION_SCREEN_V1","claim_ceiling":"type safety and order sensitivity only"})
    bp40=make_bp("e1r-transform-order-result","TRANSFORM_ORDER_RESULT_COMPLETE",[atom_record("evidence/e1r/TRANSFORM_ORDER_RESULT.json","ResultFCO","result"),atom_record("TRANSFORM_ORDER_REGISTRY.json","TransformOrderRegistryFCO","result")],{"stage":"E1R_TRANSFORM_ORDER_RESULT"},"e1r: record transform-order result",["evidence/e1r/TRANSFORM_ORDER_RESULT.json"])

    by=defaultdict(list)
    for x in temporal:by[(x["condition"],x["time"])].append(x["anticube_mean"])
    antirows=[]
    for (cond,t),xs in sorted(by.items()):antirows.append({"condition":cond,"time":t,**{k:float(np.mean([z[k] for z in xs])) for k in ("SELF_SAFE","SELF_UNSAFE","NONSELF_SAFE","NONSELF_UNSAFE","UNKNOWN")}})
    write_jsonl("evidence/e1r/ANTICUBE_TEMPORAL_RESULT.jsonl",antirows);write_json("evidence/e1r/ANTICUBE_TEMPORAL_SUMMARY.json",{"schema":"E1R_ANTICUBE_TEMPORAL_SUMMARY_V1","rows":len(antirows),"mapping":"PUBLIC_SIMULATION_ANTICUBE_E1R_V1","calibration":"NOT_INDEPENDENTLY_VALIDATED"})
    bp41=make_bp("e1r-anticube-temporal","ANTICUBE_TEMPORAL_ANALYSIS_COMPLETE",[atom_record("evidence/e1r/ANTICUBE_TEMPORAL_RESULT.jsonl","DerivedEvidenceFCO","anticube"),atom_record("evidence/e1r/ANTICUBE_TEMPORAL_SUMMARY.json","ResultSummaryFCO","anticube"),atom_record("schemas/e1r/PUBLIC_SIMULATION_ANTICUBE_E1R_V1.json","SchemaFCO","anticube")],{"stage":"E1R_ANTICUBE_TEMPORAL","independent_calibration":False},"e1r: freeze Anticube temporal analysis",["evidence/e1r/ANTICUBE_TEMPORAL_RESULT.jsonl","evidence/e1r/ANTICUBE_TEMPORAL_SUMMARY.json"])

    dg={"schema":"E1R_DELTAGSTAR_RECEIPT_V1","state":"NOT_COMPUTED","reason":"No governed private DeltaGStar implementation is present. PUBLIC_CANDIDATE_DELTAGSTAR_V1 is not substituted.","substitution_performed":False};write_json("evidence/e1r/DELTAGSTAR_NOT_COMPUTED_RECEIPT.json",dg)
    bp42=make_bp("e1r-deltagstar-state","DELTAGSTAR_NOT_COMPUTED",[atom_record("evidence/e1r/DELTAGSTAR_NOT_COMPUTED_RECEIPT.json","ExecutionReceiptFCO","delta_g")],{"stage":"E1R_DELTAGSTAR","delta_g_star":"NOT_COMPUTED"},"e1r: preserve DeltaGStar not computed",["evidence/e1r/DELTAGSTAR_NOT_COMPUTED_RECEIPT.json"])

    runtime=ROOT/"evidence/openjev/RUNTIME_MANIFEST.json";openstate="NOT_TESTED_RUNTIME_NOT_FROZEN"
    if runtime.exists():
        try:openstate="AVAILABLE_NOT_EXECUTED" if json.loads(runtime.read_text()).get("OPENJEV_LOADED")=="YES" else "NOT_TESTED_RUNTIME_NOT_LOADED"
        except Exception:openstate="NOT_TESTED_RUNTIME_MANIFEST_INVALID"
    comps=[{"id":"D0_DETERMINISTIC_ORACLE","state":"EXECUTED","calls":0},{"id":"D1_VITHIA_DETERMINISTIC_CONTEXT_POLICY","state":"EXECUTED","calls":0},{"id":"D2_OPENJEV_LOCAL","state":openstate,"provider_label":"OPENJEV_LOCAL_STANDIN","calls":0},{"id":"D3_JEV_HOSTED","state":"NOT_TESTED","calls":0},{"id":"D4_LIQUID_LOCAL","state":"NOT_TESTED","calls":0},{"id":"D5_OLLAMA_OLLARMA","state":"NOT_TESTED","calls":0}]
    write_json("SYSTEM1_COMPARATOR_REGISTRY.json",{"schema":"SYSTEM1_COMPARATOR_REGISTRY_V1","comparators":comps,"model_weight_updates":False})
    bp43=make_bp("e1r-system1-runtime","SYSTEM1_COMPARATOR_RUNTIME_STATE_FROZEN",[atom_record("SYSTEM1_COMPARATOR_REGISTRY.json","ComparatorRegistryFCO","system1"),atom_record("evidence/openjev/UPSTREAM_IDENTITY.json","ExternalModelIdentityFCO","system1")],{"stage":"E1R_SYSTEM1_RUNTIME_FREEZE","openjev_state":openstate,"model_calls":0},"e1r: freeze System-1 comparator availability",["SYSTEM1_COMPARATOR_REGISTRY.json"])
    write_json("evidence/e1r/SYSTEM1_PORTABILITY_RESULT.json",{"schema":"E1R_SYSTEM1_PORTABILITY_RESULT_V1","state":"PARTIAL_DETERMINISTIC_ONLY","executed":["D0_DETERMINISTIC_ORACLE","D1_VITHIA_DETERMINISTIC_CONTEXT_POLICY"],"not_tested":["D2_OPENJEV_LOCAL","D3_JEV_HOSTED","D4_LIQUID_LOCAL","D5_OLLAMA_OLLARMA"]})
    bp44=make_bp("e1r-system1-portability","SYSTEM1_PORTABILITY_PARTIAL_DETERMINISTIC_ONLY",[atom_record("evidence/e1r/SYSTEM1_PORTABILITY_RESULT.json","ResultFCO","system1"),atom_record("SYSTEM1_COMPARATOR_REGISTRY.json","ComparatorRegistryFCO","system1")],{"stage":"E1R_SYSTEM1_PORTABILITY_RESULT","model_calls":0},"e1r: record partial deterministic System-1 comparison",["evidence/e1r/SYSTEM1_PORTABILITY_RESULT.json"])

    vcc=scan_vcc();write_json("VCC_TRANSLATION_REGISTRY.json",vcc);write_text("docs/prereg/E1R_VCC_TRANSLATION.md","# E1R to VCC computational translation\n\nEvidence level is SIMULATED_COMPUTATIONAL_TRANSFORM_OF_BIOLOGICAL_DATA. No ECA rule is a biological mechanism claim. Execution requires exact recovery of governed VCC data, contexts, perturbations, frozen splits, current baseline/nulls, and custody receipts.\n")
    bp45=make_bp("e1r-vcc-translation-prereg","VCC_TRANSLATION_PREREGISTERED_EXECUTION_DEFERRED",[atom_record("VCC_TRANSLATION_REGISTRY.json","RegistryFCO","vcc"),atom_record("docs/prereg/E1R_VCC_TRANSLATION.md","PreregistrationFCO","vcc")],{"stage":"E1R_VCC_TRANSLATION_PREREG","vcc_state":vcc["state"],"biological_mechanism_claim":False},"e1r: preregister bounded VCC translation",["VCC_TRANSLATION_REGISTRY.json","docs/prereg/E1R_VCC_TRANSLATION.md"])

    figs=build_figures(perf,shortlists,confctx,compsum,temporal);write_json("evidence/e1r/FIGURE_BUILD_RECEIPT.json",figs)
    tdir="tables/e1r";h=[x for x in perf if x["context_type"]=="HORIZONTAL"];rg=defaultdict(list)
    for x in h:rg[x["rule_id"]].append(x)
    all256=[{"rule_id":r,"mean_gain_vs_sham":float(np.mean([x["antidote_gain_vs_sham"] for x in rs])),"mean_exact_rate":float(np.mean([x["antidote_exact_rate"] for x in rs])),"mean_context_rate":float(np.mean([x["antidote_context_rate"] for x in rs])),"mean_functional_rate":float(np.mean([x["antidote_functional_rate"] for x in rs])),"mean_neutral_entropy":float(np.mean([x["neutral_entropy"] for x in rs])),"mean_harm_rate":float(np.mean([x["antidote_harm_rate"] for x in rs]))} for r,rs in sorted(rg.items())]
    csv_file(tdir+"/T-E1R-1_all256_rule_summary.csv",all256);csv_file(tdir+"/T-E1R-2_context_pareto.csv",[{"context":c,"pareto_rules":v["pareto_rules"],"shortlist":v["shortlist"]} for c,v in shortlists.items()])
    csv_file(tdir+"/T-E1R-3_restoration_definitions.csv",[{"metric":"R_EXACT","definition":"bitwise equality"},{"metric":"R_SHIFT","definition":"zero Hamming under shifts -3..3"},{"metric":"R_CONTEXT","definition":"same frozen density/transition bins"},{"metric":"R_FUNCTIONAL","definition":"same safe-action signature"},{"metric":"R_TRAJECTORY","definition":"normalized Hamming divergence/AUD"}])
    csv_file(tdir+"/T-E1R-4_confirmatory_statistics.csv",confctx);csv_file(tdir+"/T-E1R-5_rule_composition.csv",compsum);csv_file(tdir+"/T-E1R-6_transform_order.csv",orders);csv_file(tdir+"/T-E1R-7_system1_comparators.csv",comps);csv_file(tdir+"/T-VCC-1_arms.csv",vcc["arms"])
    csv_file(tdir+"/T-LIMIT.csv",[{"item":"DeltaGStar","state":"NOT_COMPUTED"},{"item":"OpenJEV","state":openstate},{"item":"Hosted JEV","state":"NOT_TESTED"},{"item":"VCC translation","state":vcc["state"]},{"item":"Wolfram class labels","state":"UNKNOWN_NOT_INGESTED"}])
    tables=sorted(str(p.relative_to(ROOT)) for p in (ROOT/tdir).glob("*.csv"))

    led=json.loads((ROOT/"governance/MMR_LEDGER.json").read_text());last=led["entries"][-1]
    handoff={"schema":"E1R_DAISY_HANDOFF_V1","current_parent_state":{"commit":PARENT_COMMIT,"breakpoint":PARENT_BP,"mmr_root":PARENT_MMR_ROOT},"branch":BRANCH,"all_256_screen_state":"COMPLETE_SCREENING","total_runs":{"horizontal_case_rows":len(hrows),"vertical_case_rows":len(vrows),"pilot_total_case_rows":len(hrows)+len(vrows),"confirmatory_rows":len(confrows),"composition_rows":len(comprows)},"rule_context_dataset_id":ds,"rule_context_dataset_root":mf["fmo_root"],"top_context_rules":"RULE_CONTEXT_REGISTRY.json","pareto_rule_sets":base+"/PARETO_RULE_SETS.json","rule_selection_result":confover,"rule_pair_results":obase+"/pair_context_summary.jsonl","order_cross_results":"evidence/e1r/TRANSFORM_ORDER_RESULT.json","anticube_temporal_results":"evidence/e1r/ANTICUBE_TEMPORAL_RESULT.jsonl","delta_g_star_state":"NOT_COMPUTED","openjev_state":openstate,"jev_state":"NOT_TESTED","vithia_comparator_state":"EXECUTED_DETERMINISTIC_CONTEXT_POLICY","vcc_translation_state":vcc["state"],"nulls":[x for x in confctx if x["state"]=="FAIL_TO_REJECT_H0"],"negatives":[x for x in confctx if x["state"]=="NEGATIVE"],"abstains":[{"id":"O_ANTICUBE_THEN_ECA","state":"ABSTAIN_TYPE_ERROR"}],"not_tested":["DELTAGSTAR","JEV_HOSTED","LIQUID_LOCAL","OLLAMA_OLLARMA","VCC_EXECUTION"]+([] if openstate.startswith("AVAILABLE") else ["OPENJEV_LOCAL"]),"breakpoints_created":[e["bp_id"] for e in led["entries"] if int(e["bp_id"].split("-")[-1])>=29],"mmr_size":last["mmr_size"],"mmr_root":last["mmr_root_after"],"signature_state":"NOT_SIGNED","figures":figs,"tables":tables}
    write_json("E1R_DAISY_HANDOFF.json",handoff);atoms=[atom_record("E1R_DAISY_HANDOFF.json","HandoffFCO","handoff"),atom_record("RULE_CONTEXT_REGISTRY.json","RegistryFCO","handoff"),atom_record("RULE_FCO_REGISTRY.json","RegistryFCO","handoff"),atom_record("RESTORATION_RESULT_REGISTRY.json","RegistryFCO","handoff"),atom_record("TRANSFORM_ORDER_REGISTRY.json","RegistryFCO","handoff"),atom_record("SYSTEM1_COMPARATOR_REGISTRY.json","RegistryFCO","handoff"),atom_record("VCC_TRANSLATION_REGISTRY.json","RegistryFCO","handoff"),atom_record("evidence/e1r/FIGURE_BUILD_RECEIPT.json","ExecutionReceiptFCO","handoff")]
    for p in figs.get("files",[]):atoms.append(atom_record(p,"FigureFCO","figures"))
    for p in tables:atoms.append(atom_record(p,"TableFCO","tables"))
    bp46=make_bp("e1r-handoff","E1R_DAISY_SUCCESSOR_COMPLETE_BOUNDED",atoms,{"stage":"E1R_FINAL_HANDOFF","all256_screen":"COMPLETE_SCREENING","rule_selection":confover["state"],"rule_composition":"COMPLETE_SCREENING","delta_g_star":"NOT_COMPUTED","openjev":openstate,"vcc_translation":vcc["state"]},"e1r: seal restoration successor handoff",["E1R_DAISY_HANDOFF.json","RULE_CONTEXT_REGISTRY.json","RULE_FCO_REGISTRY.json","RESTORATION_RESULT_REGISTRY.json","TRANSFORM_ORDER_REGISTRY.json","SYSTEM1_COMPARATOR_REGISTRY.json","VCC_TRANSLATION_REGISTRY.json","evidence/e1r/FIGURE_BUILD_RECEIPT.json","figures/e1r","tables/e1r"])

    led=json.loads((ROOT/"governance/MMR_LEDGER.json").read_text());leaves=[]
    for i,e in enumerate(led["entries"]):
        p=ROOT/e["bp_file"];fsha,_=sha256_file(p)
        if fsha!=e["bp_file_sha256"]:raise RuntimeError("final bp file mismatch "+e["bp_id"])
        if e["root_kind"]=="FMO_V1_BREAKPOINT_ATOMS" and int(e["bp_id"].split("-")[-1])>=29:
            d=json.loads(p.read_text());groups=defaultdict(list)
            for a in d["atoms"]:
                q=ROOT/a["path"]
                if not q.exists():raise RuntimeError("missing new atom "+a["path"])
                sha,n=sha256_file(q)
                if sha!=a["sha256"] or n!=a["bytes"]:raise RuntimeError("changed new atom "+a["path"])
                groups[a["group"]].append((a["path"],leaf(a["path"],a["bytes"],a["sha256"])))
            root,_=fmo_root(dict(groups))
            if root!=e["bp_root"]:raise RuntimeError("new root mismatch "+e["bp_id"])
        lf=mmr_leaf(i,e["bp_id"],e["bp_root"],fsha);leaves.append(lf);mr,_=mmr_root(leaves)
        if mr!=e["mmr_root_after"]:raise RuntimeError("final MMR mismatch "+e["bp_id"])
    final,_=mmr_root(leaves);run([str(SHARED_PY),"-m","pytest","-q"],env=env);run([str(SHARED_PY),"scripts/secret_scan.py"],env=env)
    status("FINAL","PASS",head=run(["git","rev-parse","HEAD"],capture=True).stdout.strip(),mmr_size=len(leaves),mmr_root=final,rule_selection_state=confover["state"],openjev_state=openstate,vcc_state=vcc["state"])
    print("E1R_COMPLETE=YES");print("BRANCH="+BRANCH);print("HEAD="+run(["git","rev-parse","HEAD"],capture=True).stdout.strip());print("MMR_SIZE="+str(len(leaves)));print("MMR_ROOT="+final);print("RULE_CONTEXT_DATASET_ROOT="+mf["fmo_root"]);print("RULE_SELECTION_STATE="+confover["state"]);print("DELTAGSTAR_STATE=NOT_COMPUTED");print("OPENJEV_STATE="+openstate);print("VCC_TRANSLATION_STATE="+vcc["state"]);print("SIGNATURE_STATE=NOT_SIGNED")

if __name__=="__main__":
    try:main()
    except Exception as e:
        status("FAILED","FAIL",error=repr(e));raise
