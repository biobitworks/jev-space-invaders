#!/usr/bin/env python3
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from src.fmo import fmo_root, leaf, mmr_leaf, mmr_root, sha256_file

ROOT=Path(__file__).resolve().parents[1]
BP_DIR=ROOT/"governance"/"publication"/"breakpoints"
LEDGER=ROOT/"governance"/"publication"/"MMR_LEDGER.json"
BP_DIR.mkdir(parents=True,exist_ok=True)

def atom_record(rel_path,kind,group):
    p=ROOT/rel_path
    sha,n=sha256_file(p)
    return {"path":rel_path,"kind":kind,"group":group,"bytes":n,"sha256":sha,
            "location":"public","fmo_leaf":leaf(rel_path,n,sha).hex()}

def latest_number():
    xs=[int(p.name[:4]) for p in BP_DIR.glob("[0-9][0-9][0-9][0-9]-*.json")]
    return max(xs) if xs else 0

def atoms_root(atoms):
    groups={}
    for a in atoms:
        groups.setdefault(a["group"],[]).append((a["path"],bytes.fromhex(a["fmo_leaf"])))
    return fmo_root(groups)

def load_ledger():
    if LEDGER.exists(): return json.loads(LEDGER.read_text())
    return {"schema":"VITA_PUBLICATION_MMR_LEDGER_V1",
            "protocol":"scripts/publication_breakpoints.py",
            "entries":[]}

def create(slug,state,atoms,body):
    n=latest_number()+1
    bp_id=f"VITA-PUB-BP-{n:04d}"
    if n==1:
        parent=body.get("scientific_parent","SCIENTIFIC_PARENT_REQUIRED")
    else:
        parent=f"VITA-PUB-BP-{n-1:04d}"
    root,group_roots=atoms_root(atoms)
    doc={"breakpoint_id":bp_id,"parent":parent,"state":state,"project":"VITHIA_0_VITA_1_PUBLICATION",
         "created_utc":datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "root_kind":"FMO_V1_PUBLICATION_BREAKPOINT_ATOMS","bp_root":root,"group_roots":group_roots,
         "atoms":atoms,**body,
         "claim_ceiling":"IDENTITY_AND_INCLUSION_ONLY; publication roots do not establish scientific truth",
         "signature_state":"NOT_SIGNED"}
    path=BP_DIR/f"{n:04d}-{slug}.json"
    if path.exists(): raise SystemExit(f"{path} exists")
    path.write_text(json.dumps(doc,indent=2)+"\n")
    led=load_ledger()
    seq=len(led["entries"])
    fsha,_=sha256_file(path)
    lf=mmr_leaf(seq,bp_id,root,fsha)
    leaves=[bytes.fromhex(x["mmr_leaf"]) for x in led["entries"]]+[lf]
    mroot,peaks=mmr_root(leaves)
    ent={"seq":seq,"bp_id":bp_id,"bp_file":str(path.relative_to(ROOT)),
         "bp_file_sha256":fsha,"bp_root":root,"root_kind":doc["root_kind"],
         "mmr_leaf":lf.hex(),"mmr_size":len(leaves),"mmr_root_after":mroot,"mmr_peaks_after":peaks}
    led["entries"].append(ent); LEDGER.write_text(json.dumps(led,indent=2)+"\n")
    return {"bp_file":str(path.relative_to(ROOT)),**ent}
