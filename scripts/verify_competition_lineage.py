#!/usr/bin/env python3
from __future__ import annotations
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from src.fmo import fmo_root,leaf,mmr_leaf,mmr_root,sha256_file
LP=ROOT/"governance/lineage/UFA_JEV_COMP_MMR_LEDGER.json"
def main():
 j=json.loads(LP.read_text()); errors=[]; leaves=[]
 assert j["lineage_id"]=="UFA-JEV-COMP"
 if j.get("predecessor_roots_are_mmr_leaves") is not False: errors.append("PREDECESSOR_MMR_CONFLATION")
 for i,e in enumerate(j["entries"]):
  if e["seq"]!=i: errors.append(f"SEQ:{e[bp_id]}")
  p=ROOT/e["bp_file"]; doc=json.loads(p.read_text()); fsha,_=sha256_file(p)
  if fsha!=e["bp_file_sha256"]: errors.append(f"BP_FILE_SHA:{e[bp_id]}")
  for k in ("lineage_id","branch","parent_root","breakpoint_id","breakpoint_root"):
   if k not in doc: errors.append(f"OCCURRENCE_FIELD:{e[bp_id]}:{k}")
  groups={}
  for a in doc["atoms"]:
   ap=ROOT/a["path"]; sha,n=sha256_file(ap)
   if sha!=a["sha256"] or n!=a["bytes"]: errors.append(f"ATOM_CHANGED:{a[path]}")
   lf=leaf(a["path"],a["bytes"],a["sha256"])
   if lf.hex()!=a["fmo_leaf"]: errors.append(f"LEAF:{a[path]}")
   groups.setdefault(a["group"],[]).append((a["path"],lf))
  root,_=fmo_root(groups)
  if root!=e["bp_root"] or root!=doc["bp_root"]: errors.append(f"BP_ROOT:{e[bp_id]}")
  lf=mmr_leaf(i,e["bp_id"],root,fsha); leaves.append(lf)
  if lf.hex()!=e["mmr_leaf"]: errors.append(f"MMR_LEAF:{e[bp_id]}")
  after,_=mmr_root(leaves)
  if after!=e["mmr_root_after"]: errors.append(f"MMR_ROOT_AFTER:{e[bp_id]}")
 final,_=mmr_root(leaves)
 print("COMP_LINEAGE_ID="+j["lineage_id"])
 print("COMP_MMR_SIZE="+str(len(leaves)))
 print("COMP_MMR_ROOT="+final)
 print("COMP_BREAKPOINT_VERIFY="+("PASS" if not errors else "FAIL"))
 for x in errors: print(x)
 return 0 if not errors else 2
if __name__=="__main__": raise SystemExit(main())
