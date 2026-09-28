#!/usr/bin/env python3
import json
from pathlib import Path
R=Path(__file__).resolve().parents[1]
base=json.loads((R/"vita01/PUBLICATION_CLAIM_LEDGER.json").read_text())["entries"]
claims=[]
for e in base:
    state=e["state"]
    allowed=f"{e['claim']} is reported as {state} in the confirmatory {e['experiment_id']} receipt."
    claims.append({"claim_id":f"{e['experiment_id']}::{e['claim']}","claim":e["claim"],"experiment":e["experiment_id"],
      "state":state,"evidence_level":e["evidence_level"],"evidence_refs":[e["receipt"]],
      "allowed_wording":allowed,"forbidden_stronger_wording":"Do not upgrade beyond the recorded state."})
extra=[
 {"claim_id":"ARCH::S0_ROLE","claim":"Vithia-S0 is a context compiler; downstream S1 performs decisions.","state":"IMPLEMENTED",
  "evidence_level":"SIMULATED","evidence_refs":["vita01/VITA01_TERMINOLOGY_V2.json","vita01/S01_PROTOCOL_SPEC_DRAFT.md"],
  "allowed_wording":"The public protocol separates deterministic context compilation from downstream decision-making.",
  "forbidden_stronger_wording":"Do not claim the downstream world or model is deterministic."},
 {"claim_id":"GOV::MMR24","claim":"The scientific lineage is committed through UFA-JEV-BP-0024 in a verified MMR.","state":"OBSERVED",
  "evidence_level":"CUSTODY","evidence_refs":["governance/MMR_LEDGER.json","governance/breakpoints/0024-cross-host-replication-result.json"],
  "allowed_wording":"The repository verifier reconstructs the ordered breakpoint MMR through BP-0024.",
  "forbidden_stronger_wording":"Do not equate MMR inclusion with truth or correctness."},
 {"claim_id":"STAT::SECONDARY","claim":"Post-confirmatory secondary statistics were computed from frozen E1-E3 outputs without mutating original claims.","state":"OBSERVED",
  "evidence_level":"SIMULATED","evidence_refs":["evidence/statistical_successor/STATISTICAL_ANALYSIS.json","governance/breakpoints/0022-d0-d9-statistical-analysis-result.json"],
  "allowed_wording":"Secondary uncertainty/effect summaries supplement, but do not replace, the confirmatory decisions.",
  "forbidden_stronger_wording":"Do not recast secondary analyses as preregistered confirmatory endpoints."},
 {"claim_id":"LIMIT::E4A","claim":"E4A freezes Space Invaders snapshots and contains no decider calls.","state":"INPUT_FROZEN_NO_DECIDER_CALLS",
  "evidence_level":"SIMULATED","evidence_refs":["governance/breakpoints/0020-e4a-prereg.json"],
  "allowed_wording":"E4A supplies a frozen partially observed testbed; downstream model utility remains untested in v0.1.0.",
  "forbidden_stronger_wording":"Do not claim JEV/OpenJEV/System-1 utility from E4A."},
 {"claim_id":"LIMIT::DELTAGSTAR","claim":"DeltaGStar was not computed in the completed v0.1.0 evidence chain.","state":"NOT_COMPUTED",
  "evidence_level":"SIMULATED","evidence_refs":["vita01/VITA01_CONFIRMATORY_PREREGISTRATION.md"],
  "allowed_wording":"DeltaGStar remains a proposed/private successor component and is not an empirical result here.",
  "forbidden_stronger_wording":"Do not report DeltaGStar values or effects."},
 {"claim_id":"LIMIT::CROSSHOST","claim":"Cross-host replication was deferred because magicPRObox was unavailable.","state":"DEFERRED_NOT_FAILED",
  "evidence_level":"REPLICATION","evidence_refs":["evidence/cross_host/CROSS_HOST_REPLICATION_RECEIPT.json"],
  "allowed_wording":"Cross-host replication is deferred and does not alter the single-host confirmatory results.",
  "forbidden_stronger_wording":"Do not claim independent two-host byte-identical replication."}
]
claims+=extra
out={"schema":"VITHIA_PUBLICATION_CLAIM_MATRIX_V1","coverage_policy":"every substantive manuscript claim must reference one or more evidence_refs","entries":claims}
(R/"publication/CLAIM_MATRIX.json").write_text(json.dumps(out,indent=2)+"\n")
print(len(claims))
