"""E2 Conway Life: immutable source atoms, multi-scale context. See docs/prereg/E2_LIFE.md."""
from __future__ import annotations

import numpy as np

from experiments.common import ds_dir, prereg_ref, read_jsonl, rseed, write_jsonl, write_manifest
from src.kernels import life
from src.s01.canon import content_id

EXP, IN_ID, OUT_ID = "E2_LIFE", "S01_LIFE_CONTEXT_EVAL_V1", "S01_LIFE_CONTEXT_RESULTS_V1"
H = W = 32
CODE = ["experiments/e2_life.py", "src/kernels/life.py", "src/s01/canon.py"]

FAMILIES = {
    "still": ["block", "beehive", "loaf", "boat", "tub"],
    "oscillator": ["blinker", "toad", "beacon"],
    "glider": ["glider"],
    "spaceship": ["lwss"],
}


def scene(name: str) -> tuple[np.ndarray, int]:
    if name == "glider_block":
        g = life.place(life.parse(life.CATALOGUE_CELLS["glider"]), H, W, 4, 4)
        return life.place(life.parse(life.CATALOGUE_CELLS["block"]), H, W, 14, 13, g), 96
    if name == "glider_glider":
        g = life.place(life.parse(life.CATALOGUE_CELLS["glider"]), H, W, 4, 4)
        opp = np.fliplr(life.parse(life.CATALOGUE_CELLS["glider"]))
        return life.place(opp, H, W, 4, 16, g), 96
    return life.place(life.parse(life.CATALOGUE_CELLS[name]), H, W, 13, 13), 64


def grid_atom(g: np.ndarray) -> dict:
    return {"kind": "SourceAtomFCO", "domain": "life", "shape": list(g.shape),
            "bits_hex": np.packbits(g).tobytes().hex()}


def bbox_cells(g: np.ndarray):
    ys, xs = np.nonzero(g)
    return [(y, x) for y in range(ys.min() - 1, ys.max() + 2) for x in range(xs.min() - 1, xs.max() + 2)]


def build_input() -> dict:
    rows = []
    fams = {**FAMILIES, "collision": ["glider_block", "glider_glider"]}
    for fam, names in fams.items():
        for name in names:
            g, T = scene(name)
            cells = bbox_cells(g)
            rows.append({"scene": name, "family": fam, "T": T, "source_atom": grid_atom(g),
                         "perturbations": [[int(y) % H, int(x) % W] for y, x in cells]})
            rng = np.random.default_rng(rseed("E2mask", name))
            masks = []
            for frac in (0.10, 0.25):
                for rep in range(5):
                    k = max(1, round(frac * len(cells)))
                    idx = rng.choice(len(cells), size=k, replace=False)
                    masks.append({"frac": frac, "rep": rep, "hidden": [[cells[i][0] % H, cells[i][1] % W] for i in sorted(idx)]})
            rows[-1]["masks"] = masks
    d = ds_dir(IN_ID)
    write_jsonl(d / "rows.jsonl", rows)
    return write_manifest(d, dataset_id=IN_ID, schema="rows: {scene, family, T, source_atom, perturbations[[y,x]], masks[]}",
                          kind="evaluation", source="generated", generation_code=CODE,
                          config={"grid": [H, W], "topology": "torus", "rule": "B3/S23"},
                          seeds={"masks": "sha256(E2mask|scene)[:8]"}, claim_ceiling="deterministic synthetic patterns")


def trajectory(g: np.ndarray, T: int) -> list[np.ndarray]:
    out = [g]
    for _ in range(T):
        out.append(life.step(out[-1]))
    return out


def run() -> dict:
    out, hist_rows, invariant_ok, mask_acc = [], [], True, {0.10: [], 0.25: []}
    for r in read_jsonl(ds_dir(IN_ID) / "rows.jsonl"):
        atom = r["source_atom"]
        atom_id_before = content_id(atom)
        g0 = np.unpackbits(np.frombuffer(bytes.fromhex(atom["bits_hex"]), np.uint8))[:H * W].reshape(H, W)
        T = r["T"]
        ref = trajectory(g0, T)
        ref_objs = [life.objects(x) for x in ref]
        for y, x in r["perturbations"]:
            g = g0.copy()
            g[y, x] ^= 1
            traj = trajectory(g, T)
            first = {"CELL": None, "LOCAL_PATTERN": None, "PERSISTENT_OBJECT": None}
            for t in range(T + 1):
                if first["CELL"] is None and not np.array_equal(traj[t], ref[t]):
                    first["CELL"] = t
                if first["LOCAL_PATTERN"] is None and life.local_pattern(traj[t], y, x) != life.local_pattern(ref[t], y, x):
                    first["LOCAL_PATTERN"] = t
                if first["PERSISTENT_OBJECT"] is None and life.objects(traj[t]) != ref_objs[t]:
                    first["PERSISTENT_OBJECT"] = t
            fin, rfin = traj[T], ref[T]
            if np.array_equal(fin, rfin):
                outcome = "recovered"
            elif not fin.any() and rfin.any():
                outcome = "destroyed"
            elif set(life.objects(fin)) - set(ref_objs[T]):
                outcome = "new_structure"
            else:
                outcome = "changed"
            out.append({"scene": r["scene"], "family": r["family"], "type": "one_cell",
                        "source_cell": [y, x], "old": int(g0[y, x]), "new": int(g[y, x]),
                        "local_before": life.local_pattern(g0, y, x), "local_after": life.local_pattern(g, y, x),
                        "objects_t0_before": ref_objs[0], "objects_t0_after": life.objects(g),
                        "first_divergence": first, "outcome": outcome,
                        "objects_T": life.objects(fin)})
        for mk in r["masks"]:
            vis = g0.copy()
            for y, x in mk["hidden"]:
                vis[y, x] = 0
            correct = life.objects(vis) == ref_objs[0]
            mask_acc[mk["frac"]].append(correct)
            out.append({"scene": r["scene"], "family": r["family"], "type": "mask", "frac": mk["frac"],
                        "rep": mk["rep"], "objects_visible": life.objects(vis), "correct": correct})
        hrng = np.random.default_rng(rseed("E2hist", r["scene"]))
        for t in (8, 16, 32, 48, 64):
            if t > T:
                continue
            hist = ref[t - 4:t + 1]
            past = [hist[i] for i in hrng.permutation(len(hist) - 1)]
            conds = {"CORRECT_HISTORY": life.kinematics(hist), "SHUFFLED_HISTORY": life.kinematics(past + [hist[-1]]),
                     "NO_HISTORY": life.kinematics([hist[-1]])}
            cur_id = content_id(grid_atom(hist[-1]))
            for name, kin in conds.items():
                labelled = [k for k in kin if k["object"] in life.TRUE_MOTION]
                correct = sum(k["motion"] == life.TRUE_MOTION[k["object"]] for k in labelled)
                hist_rows.append({"scene": r["scene"], "t": t, "condition": name, "current_atom_id": cur_id,
                                  "kinematics": kin, "labelled": len(labelled), "correct": correct,
                                  "unknown": sum(k["motion"] == "UNKNOWN" for k in labelled)})
        invariant_ok &= content_id(atom) == atom_id_before
    d = ds_dir(OUT_ID)
    sha, _, nrows = write_jsonl(d / "rows.jsonl", out)
    write_jsonl(d / "history_controls.jsonl", hist_rows)

    def acc(cond):
        rows = [h for h in hist_rows if h["condition"] == cond]
        lab = sum(h["labelled"] for h in rows)
        return (sum(h["correct"] for h in rows) / lab if lab else None), (sum(h["unknown"] for h in rows) / lab if lab else None)

    a_c, _ = acc("CORRECT_HISTORY")
    a_s, _ = acc("SHUFFLED_HISTORY")
    _, u_n = acc("NO_HISTORY")
    same_atom_diff_ctx = sum(1 for h in hist_rows if h["condition"] == "CORRECT_HISTORY"
                             for g in hist_rows if g["condition"] == "NO_HISTORY" and g["scene"] == h["scene"]
                             and g["t"] == h["t"] and g["current_atom_id"] == h["current_atom_id"] and g["kinematics"] != h["kinematics"])
    acc10 = sum(mask_acc[0.10]) / len(mask_acc[0.10])
    acc25 = sum(mask_acc[0.25]) / len(mask_acc[0.25])
    outcomes = {}
    for o in out:
        if o["type"] == "one_cell":
            outcomes.setdefault(o["family"], {}).setdefault(o["outcome"], 0)
            outcomes[o["family"]][o["outcome"]] += 1
    claims = [
        {"id": "H2a", "state": "SUPPORTED" if invariant_ok else "NOT_SUPPORTED"},
        {"id": "H2b", "state": "SUPPORTED" if acc25 <= acc10 else "NOT_SUPPORTED",
         "mask_accuracy_10": round(acc10, 4), "mask_accuracy_25": round(acc25, 4)},
        {"id": "H2c", "state": "OBSERVED", "outcomes_by_family": outcomes},
        {"id": "H2d", "state": "SUPPORTED" if (a_c is not None and a_c >= 0.95 and u_n == 1.0 and a_s < a_c) else "NOT_SUPPORTED",
         "accuracy_correct_history": a_c, "accuracy_shuffled_history": a_s, "unknown_rate_no_history": u_n,
         "same_current_atom_different_context": same_atom_diff_ctx,
         "status": "NEW successor hypothesis (P3 history sensitivity), post-rehearsal prospective (not blind)"},
    ]
    m = write_manifest(d, dataset_id=OUT_ID, schema="rows: one_cell {...first_divergence, outcome} | mask {...correct}",
                       kind="output", source=IN_ID, generation_code=CODE, config={}, seeds=[],
                       parent_evidence=[IN_ID], claim_ceiling="deterministic rule dynamics; no biological or emergence claim")
    terminal = "SUPPORTED" if all(c["state"] in ("SUPPORTED", "OBSERVED") for c in claims) else "PARTIAL"
    return {"experiment_id": EXP, "question": "Can exact lower-level atoms remain immutable while higher-order deterministic context changes across scales?",
            "preregistration": prereg_ref("E2_LIFE.md"), "output_manifest": m, "terminal_state": terminal,
            "claims": claims, "output_rows_sha256": sha, "rows": nrows, "not_tested": []}
