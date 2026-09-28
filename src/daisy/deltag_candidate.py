"""PUBLIC_CANDIDATE_DELTAGSTAR_V1: a public, versioned diagnostic. It is NOT the governed/private ΔG*.

Frozen definition (deltag_candidate_v1.json):
  U*      = 1 if the chosen action has no surviving continuation to the oracle horizon, else 0
  H_norm  = Shannon entropy of the decider's returned action probabilities / log2(|legal actions|)
  G*      = U* - tau * H_norm, tau = 1
  ref     = uniform-random decider on the same state: U*_ref = mean over actions of U*, H_norm_ref = 1
  ΔG*     = G*(decider) - G*(ref)
Computed only when real decider probabilities exist; otherwise NOT_COMPUTED (never fabricated).
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

DEF_PATH = Path(__file__).resolve().parents[2] / "schemas" / "daisy" / "deltag_candidate_v1.json"
DEFINITION = json.loads(DEF_PATH.read_text())
DEFINITION_ID = "PUBLIC_CANDIDATE_DELTAGSTAR_V1:sha256:" + hashlib.sha256(DEF_PATH.read_bytes()).hexdigest()


def compute(probabilities, unsafe_by_action: dict, chosen: str) -> dict:
    if not isinstance(probabilities, dict) or not probabilities or chosen not in unsafe_by_action:
        return {"delta_G_star": "NOT_COMPUTED", "reason": "no decider probabilities", "delta_g_definition_id": DEFINITION_ID}
    n = len(unsafe_by_action)
    p = [float(probabilities.get(a, 0.0)) for a in unsafe_by_action]
    s = sum(p)
    if s <= 0:
        return {"delta_G_star": "NOT_COMPUTED", "reason": "probabilities sum to 0", "delta_g_definition_id": DEFINITION_ID}
    p = [x / s for x in p]
    h = -sum(x * math.log2(x) for x in p if x > 0) / math.log2(n)
    tau = DEFINITION["tau"]
    u = float(unsafe_by_action[chosen])
    g = u - tau * h
    g_ref = sum(float(v) for v in unsafe_by_action.values()) / n - tau * 1.0
    return {"U_star": u, "H_norm": round(h, 6), "G_star": round(g, 6), "reference_G_star": round(g_ref, 6),
            "delta_G_star": round(g - g_ref, 6), "delta_g_definition_id": DEFINITION_ID}
