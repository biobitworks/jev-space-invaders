#!/usr/bin/env python3
from __future__ import annotations
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from src.fmo import fmo_root,leaf,mmr_leaf,mmr_root,sha256_file
LEDGER=ROOT/"governance/publication/MMR_LEDGER.json"
if not LEDGER.exists():
    print("PUBLICATION_BREAKPOINT_VERIFY=FAIL\nNO_LEDGER"); raise SystemExit(2)
led=json.loads(LEDGER.read_text()); errors=[]; leaves=[]
for i,e in enumerate(led["entries"]):
    p=ROOT/e["bp_file"]; d=json.loads(p.read_text())
    groups={}
    for a in d["atoms"]:
        q=ROOT/a["path"]
        if not q.exists(): errors.append("MISSING:"+a["path"]); continue
        sha,n=sha256_file(q)
        if sha!=a["sha256"] or n!=a["bytes"]: errors.append("CHANGED:"+a["path"])
        lf=leaf(a["path"],a["bytes"],a["sha256"])
        if lf.hex()!=a["fmo_leaf"]: errors.append("LEAF:"+a["path"])
        groups.setdefault(a["group"],[]).append((a["path"],lf))
    root,_=fmo_root(groups)
    if root!=d["bp_root"] or root!=e["bp_root"]: errors.append("ROOT:"+e["bp_id"])
    fsha,_=sha256_file(p)
    if fsha!=e["bp_file_sha256"]: errors.append("BP_FILE:"+e["bp_id"])
    mlf=mmr_leaf(i,e["bp_id"],root,fsha); leaves.append(mlf)
    if mlf.hex()!=e["mmr_leaf"]: errors.append("MMR_LEAF:"+e["bp_id"])
    mr,_=mmr_root(leaves)
    if mr!=e["mmr_root_after"]: errors.append("MMR_ROOT:"+e["bp_id"])
    print(e["bp_id"],root,e["mmr_root_after"])
final,_=mmr_root(leaves)
print("PUBLICATION_MMR_SIZE="+str(len(leaves)))
print("PUBLICATION_MMR_ROOT="+final)
print("PUBLICATION_BREAKPOINT_VERIFY="+("PASS" if not errors else "FAIL"))
for x in errors: print(x)
raise SystemExit(0 if not errors else 2)
