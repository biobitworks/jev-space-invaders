"""E3 Minesweeper: epistemic uncertainty over a determined hidden world. See docs/prereg/E3_MINESWEEPER.md."""
from __future__ import annotations

import math
import random
import time

from experiments.common import ds_dir, prereg_ref, read_jsonl, rseed, write_jsonl, write_manifest
from src.kernels import minesweeper as ms

EXP, IN_ID, OUT_ID = "E3_MINESWEEPER", "S01_MINESWEEPER_EVAL_V1", "S01_MINESWEEPER_RESULTS_V1"
SIZES = [{"name": "9x9x10", "h": 9, "w": 9, "mines": 10, "boards": 300, "start": (4, 4)},
         {"name": "16x16x40", "h": 16, "w": 16, "mines": 40, "boards": 100, "start": (8, 8)}]
PER_STRATUM = 60
N_CANDIDATES = 12
CODE = ["experiments/e3_minesweeper.py", "src/kernels/minesweeper.py", "src/s01/canon.py"]


def stratum(view: ms.View, n_mines: int) -> str:
    o = ms.oracle_labels(view, n_mines)
    forced = sum(v != "UNKNOWN" for v in o.values())
    if o and forced == len(o):
        return "determined"
    if forced:
        return "partially_determined"
    has_frontier = any(n not in view.revealed for c in view.revealed for n in view.board.neigh(c))
    return "ambiguous" if has_frontier else "guess_required"


def build_input() -> dict:
    rows = []
    for sz in SIZES:
        pool = {"determined": [], "partially_determined": [], "ambiguous": [], "guess_required": []}
        for seed in range(sz["boards"]):
            b = ms.generate(sz["h"], sz["w"], sz["mines"], seed, sz["start"])
            v = ms.View(b)
            rng = random.Random(rseed("E3play", sz["name"], seed))
            pool["guess_required"].append((seed, v.signature()))
            v.reveal(sz["start"])
            for _ in range(200):
                hidden = v.hidden()
                if len(hidden) == sz["mines"]:
                    break
                pool[stratum(v, sz["mines"])].append((seed, v.signature()))
                o = ms.oracle_labels(v, sz["mines"])
                safe = [c for c, lab in o.items() if lab == "SAFE"]
                if safe:
                    for c in safe:
                        v.reveal(c)
                else:
                    truly_safe = sorted(c for c in hidden if c not in b.mines)
                    v.reveal(rng.choice(truly_safe))
        for st, items in pool.items():
            rng = random.Random(rseed("E3sample", sz["name"], st))
            pick = rng.sample(items, min(PER_STRATUM, len(items)))
            for seed, sig in pick:
                rows.append({"size": sz["name"], "h": sz["h"], "w": sz["w"], "mines": sz["mines"],
                             "board_seed": seed, "start": list(sz["start"]), "stratum": st,
                             "revealed": sig, "pool_size": len(items)})
    d = ds_dir(IN_ID)
    write_jsonl(d / "rows.jsonl", rows)
    return write_manifest(d, dataset_id=IN_ID, schema="rows: {size,h,w,mines,board_seed,start,stratum,revealed[[y,x,clue]],pool_size}",
                          kind="evaluation", source="generated", generation_code=CODE,
                          config={"sizes": SIZES, "per_stratum": PER_STRATUM, "stratum_labeller": "SAT oracle (python-sat Minisat22)",
                                  "ontic_randomness_after_generation": "none"},
                          seeds={"boards": "range per size", "play": "sha256(E3play|size|seed)", "sample": "sha256(E3sample|size|stratum)"},
                          claim_ceiling="synthetic boards; true board recoverable from seed")


def rebuild(r) -> tuple[ms.Board, ms.View]:
    b = ms.generate(r["h"], r["w"], r["mines"], r["board_seed"], tuple(r["start"]))
    v = ms.View(b)
    for y, x, k in r["revealed"]:
        if b.clue((y, x)) != k:
            raise SystemExit("frozen clue does not match regenerated board")
        v.revealed[(y, x)] = k
    return b, v


def actual_gain(view, n, c, base, board) -> float:
    W = base["worlds"]
    if c in board.mines:
        w_after = base["p"][c] * W
    else:
        post = ms.infer(view, n, extra={c: board.clue(c)})
        w_after = post["worlds"]
    return math.log2(W) - math.log2(w_after)


def run() -> dict:
    from scipy.stats import wilcoxon

    out, timings, agree_cells, disagree_cells = [], [], 0, 0
    pairs, eig_list, act_list = [], [], []
    for i, r in enumerate(read_jsonl(ds_dir(IN_ID) / "rows.jsonl")):
        b, v = rebuild(r)
        n = r["mines"]
        t0 = time.perf_counter()
        post = ms.infer(v, n)
        k_ms = (time.perf_counter() - t0) * 1000
        t0 = time.perf_counter()
        orc = ms.oracle_labels(v, n)
        o_ms = (time.perf_counter() - t0) * 1000
        kstat = "ABSTAIN_SIZE_LIMIT" if post["status"] == "BUDGET_EXCEEDED" else post["status"]
        row = {"i": i, "size": r["size"], "stratum": r["stratum"], "kernel_status": kstat, "hidden": len(orc)}
        timings.append({"i": i, "size": r["size"], "stratum": r["stratum"], "kernel_ms": round(k_ms, 3), "oracle_ms": round(o_ms, 3)})
        if post["status"] == "OK":
            lab = ms.labels(post)
            dis = [c for c in orc if lab[c] != orc[c]]
            agree_cells += len(orc) - len(dis)
            disagree_cells += len(dis)
            row.update({"disagreements": [list(c) for c in dis], "log2_worlds": round(math.log2(post["worlds"]), 6),
                        "n_safe": sum(x == "SAFE" for x in lab.values()), "n_unsafe": sum(x == "UNSAFE" for x in lab.values()),
                        "n_unknown": sum(x == "UNKNOWN" for x in lab.values())})
            unk = sorted((c for c, x in lab.items() if x == "UNKNOWN"), key=lambda c: (post["p"][c], c))[:N_CANDIDATES]
            if len(unk) >= 2:
                eigs = {c: ms.entropy_bits(ms.outcome_distribution(v, n, c, post)) for c in unk}
                best = max(unk, key=lambda c: (eigs[c], -post["p"][c], c))
                rnd = random.Random(rseed("E3rand", i)).choice(unk)
                g_best = actual_gain(v, n, best, post, b)
                g_rnd = actual_gain(v, n, rnd, post, b)
                row["question"] = {"max_eig_cell": list(best), "eig_bits": round(eigs[best], 6),
                                   "actual_gain_bits": round(g_best, 6), "random_cell": list(rnd),
                                   "random_eig_bits": round(eigs[rnd], 6), "random_actual_gain_bits": round(g_rnd, 6),
                                   "p_mine_best": float(post["p"][best])}
                pairs.append((g_best, g_rnd))
                eig_list.append(eigs[best])
                act_list.append(g_best)
        out.append(row)
    d = ds_dir(OUT_ID)
    sha, _, nrows = write_jsonl(d / "rows.jsonl", out)
    write_jsonl(d / "timings.jsonl", timings)
    diffs = [a - b for a, b in pairs]
    p3b = float(wilcoxon(diffs, alternative="greater").pvalue) if any(diffs) else 1.0
    gap = abs(sum(act_list) / len(act_list) - sum(eig_list) / len(eig_list))
    budget = sum(o["kernel_status"] == "ABSTAIN_SIZE_LIMIT" for o in out)
    budget_cells = sum(o["hidden"] for o in out if o["kernel_status"] == "ABSTAIN_SIZE_LIMIT")
    claims = [
        {"id": "H3a", "state": "SUPPORTED" if disagree_cells == 0 else "NOT_SUPPORTED",
         "agree_cells": agree_cells, "disagree_cells": disagree_cells,
         "abstain_size_limit_states": budget, "abstain_size_limit_cells": budget_cells,
         "abstain_rule": "states above the kernel component cap are ABSTAIN_SIZE_LIMIT: not PASS, not FAIL, no SAFE/UNSAFE label",
         "oracle_identity": ms.oracle_identity()},
        {"id": "H3b", "state": "SUPPORTED" if p3b < 0.05 else "FAIL_TO_REJECT_H0", "p": p3b, "pairs": len(pairs),
         "mean_gain_max_eig": round(sum(a for a, _ in pairs) / len(pairs), 4),
         "mean_gain_random": round(sum(b for _, b in pairs) / len(pairs), 4)},
        {"id": "H3c", "state": "SUPPORTED" if gap <= 0.10 else "NOT_SUPPORTED",
         "mean_actual_gain": round(sum(act_list) / len(act_list), 4), "mean_eig": round(sum(eig_list) / len(eig_list), 4),
         "abs_gap_bits": round(gap, 4)},
    ]
    m = write_manifest(d, dataset_id=OUT_ID, schema="rows.jsonl: {i,size,stratum,kernel_status,...,question} (deterministic); timings.jsonl: {i,kernel_ms,oracle_ms} (machine-specific)",
                       kind="output", source=IN_ID, generation_code=CODE, config={}, seeds=[],
                       parent_evidence=[IN_ID], claim_ceiling="rows.jsonl deterministic; timings.jsonl machine-specific")
    terminal = "SUPPORTED" if all(c["state"] == "SUPPORTED" for c in claims) else "PARTIAL"
    return {"experiment_id": EXP, "question": "Can the same substrate represent incomplete knowledge over a fully deterministic hidden world?",
            "preregistration": prereg_ref("E3_MINESWEEPER.md"), "output_manifest": m, "terminal_state": terminal,
            "claims": claims, "output_rows_sha256": sha, "rows": nrows, "not_tested": [],
            "note": "timings are in timings.jsonl; rows.jsonl is expected to be byte-identical across runtimes"}
