"""E1 ECA rule identification. See docs/prereg/E1_ECA.md."""
from __future__ import annotations

import hashlib
import random

import numpy as np

from experiments.common import ds_dir, prereg_ref, read_jsonl, rseed, write_jsonl, write_manifest
from src.kernels.eca import evolve

EXP, IN_ID, OUT_ID = "E1_ECA", "S01_ECA_256_EVAL_V1", "S01_ECA_256_RESULTS_V1"
W, T = 64, 48
ICS = ["single", "rand1", "rand2", "rand3"]
KINDS = ["exact", "missing_cell", "bit_flip", "missing_row", "mixed"]
XCHECK = [0, 30, 54, 90, 110, 150, 184, 255]
CODE = ["experiments/e1_eca.py", "src/kernels/eca.py", "src/s01/canon.py"]
TABLE = np.array([[(r >> j) & 1 for j in range(8)] for r in range(256)], dtype=np.int64)


def initial(ic: str) -> list[int]:
    if ic == "single":
        row = [0] * W
        row[W // 2] = 1
        return row
    rng = random.Random({"rand1": 11, "rand2": 12, "rand3": 13}[ic])
    return [rng.randrange(2) for _ in range(W)]


def to_hex(row) -> str:
    return int("".join(map(str, row)), 2).to_bytes(W // 8, "big").hex()


def from_hex(h: str) -> list[int]:
    return [int(b) for b in bin(int(h, 16))[2:].zfill(W)]


def corrupt(clean: np.ndarray, kind: str, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    obs = clean.astype(np.int64).copy()
    if kind == "exact":
        return obs
    if kind in ("missing_cell", "mixed"):
        p = 0.10 if kind == "missing_cell" else 0.05
        obs[rng.random(obs.shape) < p] = -1
    if kind in ("bit_flip", "mixed"):
        p = 0.02 if kind == "bit_flip" else 0.01
        flip = (rng.random(obs.shape) < p) & (obs >= 0)
        obs[flip] = 1 - obs[flip]
    if kind in ("missing_row", "mixed"):
        every = 4 if kind == "missing_row" else 8
        obs[every::every] = -1
    return obs


def build_input() -> dict:
    rows = []
    for rule in range(256):
        for ic in ICS:
            clean = np.array(evolve(initial(ic), rule, T), dtype=np.int64)
            corr = {}
            for kind in KINDS:
                s = rseed("E1", rule, ic, kind)
                obs = corrupt(clean, kind, s)
                corr[kind] = {"seed": s, "obs_sha256": hashlib.sha256(obs.astype(np.int8).tobytes()).hexdigest()}
            rows.append({"rule": rule, "ic": ic, "clean_hex": [to_hex(r) for r in clean], "corruptions": corr})
    d = ds_dir(IN_ID)
    write_jsonl(d / "rows.jsonl", rows)
    return write_manifest(d, dataset_id=IN_ID, schema="rows: {rule, ic, clean_hex[T+1], corruptions{kind:{seed,obs_sha256}}}",
                          kind="evaluation", source="generated", generation_code=CODE,
                          config={"width": W, "steps": T, "boundary": "periodic", "ics": ICS, "kinds": KINDS,
                                  "corruption_spec": {"missing_cell": 0.10, "bit_flip": 0.02, "missing_row": "every 4th",
                                                      "mixed": "0.05 missing + 0.01 flip + every 8th row"}},
                          seeds={"rand1": 11, "rand2": 12, "rand3": 13, "corruption": "sha256(E1|rule|ic|kind)[:8]"},
                          claim_ceiling="deterministic synthetic trajectories")


def cellpylib_check() -> dict:
    try:
        import cellpylib as cpl
        from importlib.metadata import version
    except ImportError:
        return {"state": "NOT_TESTED", "reason": "cellpylib not installed"}
    mism, cells = 0, 0
    for rule in XCHECK:
        for ic in ICS:
            ours = np.array(evolve(initial(ic), rule, T))
            theirs = cpl.evolve(np.array([initial(ic)]), timesteps=T + 1,
                                apply_rule=lambda n, c, t, rule=rule: cpl.nks_rule(n, rule))
            mism += int((ours != theirs).sum())
            cells += ours.size
    return {"state": "PASS" if mism == 0 else "FAIL", "rules": XCHECK, "ics": ICS, "cells": cells,
            "mismatched_cells": mism, "cellpylib_version": version("cellpylib"),
            "reference_commit_in_intake": "743e936d48f8520f6f4ac652570ac7bb46414189",
            "note": "installed PyPI version compared; equality with the intake commit not verified"}


def split_entropy(bits: np.ndarray) -> float:
    p = bits.mean()
    return 0.0 if p in (0.0, 1.0) else float(-(p * np.log2(p) + (1 - p) * np.log2(1 - p)))


def analyse(rule: int, clean: np.ndarray, obs: np.ndarray) -> dict:
    n0, n1 = np.zeros(8, np.int64), np.zeros(8, np.int64)
    ser = {k: [] for k in ("consistent", "map", "rank", "coverage", "pred_acc", "q_eig")}
    q_final = None
    for t in range(1, T + 1):
        prev, cur = obs[t - 1], obs[t]
        if (prev >= 0).any() and (cur >= 0).any():
            l, c, r = np.roll(prev, 1), prev, np.roll(prev, -1)
            ok = (l >= 0) & (c >= 0) & (r >= 0) & (cur >= 0)
            j = (4 * l + 2 * c + r)[ok]
            b = cur[ok]
            np.add.at(n0, j[b == 0], 1)
            np.add.at(n1, j[b == 1], 1)
        mis = TABLE @ n0 + (1 - TABLE) @ n1
        mmin = mis.min()
        map_set = np.nonzero(mis == mmin)[0]
        ser["consistent"].append(int((mis == 0).sum()))
        ser["map"].append(int(map_set.size))
        ser["rank"].append(int((mis < mis[rule]).sum()) + 1)
        ser["coverage"].append(int(((n0 + n1) > 0).sum()))
        maj = (TABLE[map_set].mean(axis=0) >= 0.5).astype(np.int64)
        cl, cc, cr = np.roll(clean[t - 1], 1), clean[t - 1], np.roll(clean[t - 1], -1)
        pred = maj[4 * cl + 2 * cc + cr]
        ser["pred_acc"].append(round(float((pred == clean[t]).mean()), 4))
        eig = [split_entropy(TABLE[map_set, jj]) for jj in range(8)]
        jbest = int(np.argmax(eig))
        ser["q_eig"].append(round(eig[jbest], 4))
        q_final = {"neighbourhood": jbest, "eig_bits": round(eig[jbest], 4),
                   "observed_already": bool(n0[jbest] + n1[jbest] > 0)}
    observed = (n0 + n1) > 0
    equiv = np.nonzero((TABLE[:, observed] == TABLE[rule, observed]).all(axis=1))[0]
    return {"series": ser, "question_final": q_final, "final_map": sorted(int(x) for x in map_set),
            "equivalence_class": sorted(int(x) for x in equiv)}


def run() -> dict:
    from scipy.stats import mannwhitneyu

    xc = cellpylib_check()
    out = []
    for r in read_jsonl(ds_dir(IN_ID) / "rows.jsonl"):
        clean = np.array([from_hex(h) for h in r["clean_hex"]], dtype=np.int64)
        for kind in KINDS:
            spec = r["corruptions"][kind]
            obs = corrupt(clean, kind, spec["seed"])
            if hashlib.sha256(obs.astype(np.int8).tobytes()).hexdigest() != spec["obs_sha256"]:
                raise SystemExit(f"frozen observation mismatch rule {r['rule']} {r['ic']} {kind}")
            a = analyse(r["rule"], clean, obs)
            out.append({"rule": r["rule"], "ic": r["ic"], "kind": kind, **a})
    d = ds_dir(OUT_ID)
    sha, _, nrows = write_jsonl(d / "rows.jsonl", out)

    def sel(kind, ics):
        return [o for o in out if o["kind"] == kind and o["ic"] in ics]

    rnd = ["rand1", "rand2", "rand3"]
    ex = sel("exact", ICS)
    h1a = all(all(x == 1 for x in o["series"]["rank"]) and all(c >= 1 for c in o["series"]["consistent"]) for o in ex)
    h1b = all(o["final_map"] == o["equivalence_class"] for o in ex)
    lg = lambda o: float(np.log2(o["series"]["map"][-1]))  # noqa: E731
    a_r, a_s = [lg(o) for o in sel("exact", rnd)], [lg(o) for o in sel("exact", ["single"])]
    p1c = float(mannwhitneyu(a_r, a_s, alternative="less").pvalue)
    bf = sel("bit_flip", rnd)
    frac1d = sum(o["series"]["rank"][-1] == 1 for o in bf) / len(bf)

    def t_final(o):
        m = o["series"]["map"]
        return next(i for i, v in enumerate(m, 1) if v == m[-1])

    t_mr, t_ex = [t_final(o) for o in sel("missing_row", rnd)], [t_final(o) for o in sel("exact", rnd)]
    p1e = float(mannwhitneyu(t_mr, t_ex, alternative="greater").pvalue)
    claims = [
        {"id": "G1", "state": "SUPPORTED" if xc["state"] == "PASS" else ("NOT_TESTED" if xc["state"] == "NOT_TESTED" else "NOT_SUPPORTED"),
         "cross_check": xc},
        {"id": "H1a", "state": "SUPPORTED" if h1a else "NOT_SUPPORTED", "runs": len(ex)},
        {"id": "H1b", "state": "SUPPORTED" if h1b else "NOT_SUPPORTED", "runs": len(ex)},
        {"id": "H1c", "state": "SUPPORTED" if p1c < 0.05 else "FAIL_TO_REJECT_H0", "p": p1c,
         "median_log2_map_random": float(np.median(a_r)), "median_log2_map_single": float(np.median(a_s))},
        {"id": "H1d", "state": "SUPPORTED" if frac1d >= 0.90 else "NOT_SUPPORTED", "fraction_rank1": round(frac1d, 4), "runs": len(bf)},
        {"id": "H1e", "state": "SUPPORTED" if p1e < 0.05 else "FAIL_TO_REJECT_H0", "p": p1e,
         "median_t_missing_row": float(np.median(t_mr)), "median_t_exact": float(np.median(t_ex))},
    ]
    m = write_manifest(d, dataset_id=OUT_ID, schema="rows: {rule, ic, kind, series{...}, question_final, final_map, equivalence_class}",
                       kind="output", source=IN_ID, generation_code=CODE, config={}, seeds=[],
                       parent_evidence=[IN_ID], claim_ceiling="public reference S0 (consistency filter); private S0 NOT_TESTED")
    if xc["state"] == "FAIL":
        terminal = "FAILED"
    else:
        states = [c["state"] for c in claims[1:]]
        terminal = "SUPPORTED" if all(s == "SUPPORTED" for s in states) else "PARTIAL"
    return {"experiment_id": EXP, "question": "Can the same evidence substrate identify compatible deterministic rule universes as partial/noisy observations arrive?",
            "preregistration": prereg_ref("E1_ECA.md"), "output_manifest": m, "terminal_state": terminal,
            "claims": claims, "output_rows_sha256": sha, "rows": nrows,
            "not_tested": ["Golden-Corridor contraction (private S0)", "private context commitment"]}
