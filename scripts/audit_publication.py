#!/usr/bin/env python3
import json,re
from pathlib import Path
R=Path(__file__).resolve().parents[1]
P=R/"publication"; A=P/"audits"; A.mkdir(parents=True,exist_ok=True)
main=(P/"manuscript/main.tex").read_text()
supp=(P/"supplement/supplement.tex").read_text()
claim_matrix=json.loads((P/"CLAIM_MATRIX.json").read_text())
bindings=json.loads((P/"MANUSCRIPT_CLAIM_BINDINGS.json").read_text())["bindings"]
known={e["claim_id"]:e for e in claim_matrix["entries"]}

cite_keys=[]
for group in re.findall(r"\\cite\{([^}]+)\}",main):
    cite_keys += [x.strip() for x in group.split(",")]
bib_keys=set(re.findall(r"\\bibitem\{([^}]+)\}",main))
citation_missing=sorted(set(cite_keys)-bib_keys)
citation={"schema":"VITHIA_CITATION_AUDIT_V1","state":"PASS" if cite_keys and not citation_missing else "FAIL",
          "citation_uses":len(cite_keys),"unique_citations":sorted(set(cite_keys)),
          "bibliography_keys":sorted(bib_keys),"missing_keys":citation_missing}

claim_errors=[]; covered=set()
for b in bindings:
    cid=b["claim_id"]
    if cid not in known:
        claim_errors.append("UNKNOWN_CLAIM:"+cid); continue
    covered.add(cid)
    for ref in known[cid].get("evidence_refs",[]):
        if not (R/ref).exists(): claim_errors.append("MISSING_EVIDENCE:"+cid+":"+ref)
required={"ARCH::S0_ROLE","GOV::MMR24","STAT::SECONDARY","LIMIT::E4A","LIMIT::DELTAGSTAR","LIMIT::CROSSHOST",
          "E0_ADDRESSABILITY::H0a","E1_ECA::H1d","E2_LIFE::H2d","E3_MINESWEEPER::H3a","E3_MINESWEEPER::H3b"}
missing_required=sorted(required-covered)
claim_errors += ["UNBOUND_REQUIRED:"+x for x in missing_required]
claim_audit={"schema":"VITHIA_CLAIM_AUDIT_V1","state":"PASS" if not claim_errors else "FAIL",
             "bindings":len(bindings),"covered_claim_ids":sorted(covered),
             "required_claims":sorted(required),"errors":claim_errors,
             "coverage_rule":"all required substantive manuscript result/architecture/limitation claims are bound to governed evidence"}

text=(main+"\n"+supp).lower()
forbidden=[
 ("HASH_TRUTH","hash proves truth"),("MERKLE_TRUTH","merkle proves truth"),("MMR_TRUTH","mmr proves truth"),
 ("FCG_CAUSAL","fcg edge proves causality"),("OPENJEV_JEV","openjev is jev"),
 ("SIMULATION_BIO","simulation is biological evidence")
]
hits=[{"id":k,"phrase":v} for k,v in forbidden if v in text]
required_phrases=["not\\_computed","not\\_tested","deferred\\_not\\_failed","not\\_signed",
                  "do not establish scientific truth","no decider calls"]
missing_phrases=[x for x in required_phrases if x not in text]
type_audit={"schema":"VITHIA_TYPE_SAFETY_AUDIT_V1","state":"PASS" if not hits and not missing_phrases else "FAIL",
            "forbidden_conflation_hits":hits,"missing_required_boundary_phrases":missing_phrases,
            "checks":["identity!=meaning","custody!=correctness","prediction!=observation",
                      "MMR inclusion != truth","FCG relationship != causality","simulation != biological evidence"]}

for name,obj in [("CITATION_AUDIT.json",citation),("CLAIM_AUDIT.json",claim_audit),("TYPE_SAFETY_AUDIT.json",type_audit)]:
    (A/name).write_text(json.dumps(obj,indent=2)+"\n")
overall="PASS" if all(x["state"]=="PASS" for x in [citation,claim_audit,type_audit]) else "FAIL"
(A/"AUDIT_SUMMARY.json").write_text(json.dumps({"schema":"VITHIA_PUBLICATION_AUDIT_SUMMARY_V1","state":overall,
 "citation":citation["state"],"claim":claim_audit["state"],"type_safety":type_audit["state"]},indent=2)+"\n")
print(json.dumps({"overall":overall,"citation":citation,"claim":claim_audit,"type_safety":type_audit},indent=2))
raise SystemExit(0 if overall=="PASS" else 2)
