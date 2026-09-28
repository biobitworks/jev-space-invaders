#!/usr/bin/env python3
"""Pre-freeze design check (ground truth only, no decider): does the E4A unsafe proxy depend on the action?"""
import collections, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from experiments import e4b_ablation as e  # noqa: E402
rows = [json.loads(l) for l in open(ROOT / "data/s01/S01_SPACE_INVADERS_SNAPSHOT_EVAL_V1/rows.jsonl")]
per = []
for r in rows:
    ot = e.outcome_table(r["seed"], r["step"])
    env, _, info = e.replay(r["seed"], r["step"]); l0 = info["lives"]
    _, _, _, _, info = env.step(0)
    per.append({"snapshot": r["snapshot"], "stratum": r["stratum"], "unsafe_actions": sum(ot.values()),
                "life_lost_on_first_step": info["lives"] < l0})
c = collections.Counter(p["unsafe_actions"] for p in per)
out = {"schema": "E4A_PROXY_DISCRIMINATION_CHECK_V1", "proxy": {"repeat": e.REPEAT, "horizon_steps": e.HORIZON},
       "unsafe_actions_per_snapshot": dict(sorted(c.items())),
       "discriminating_snapshots": sum(1 for p in per if 0 < p["unsafe_actions"] < 6),
       "already_doomed_first_step": sum(p["life_lost_on_first_step"] for p in per),
       "finding": "E4A frozen unsafe proxy is non-discriminating on the frozen panel (doomed or safe under every action)",
       "claim_state": "E4A quality endpoint: NULL / METRIC_NOT_DISCRIMINATING (pre-execution design finding)", "rows": per}
(ROOT / "evidence/e4b").mkdir(exist_ok=True)
(ROOT / "evidence/e4b/E4A_PROXY_DISCRIMINATION_CHECK.json").write_text(json.dumps(out, indent=2) + "\n")
print({k: out[k] for k in ("unsafe_actions_per_snapshot", "discriminating_snapshots", "already_doomed_first_step")})
