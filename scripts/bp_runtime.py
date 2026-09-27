#!/usr/bin/env python3
"""ROM_BOUND_RUNTIME breakpoint (numbered after the latest existing breakpoint).

1. Hash the installed runtime (ale-py incl. bundled ROM, gymnasium, numpy, deps,
   interpreter) into a successor RuntimeSourceDataset with its own FMO root.
2. Determinism smoke: seeds 1-5, 100 steps of a fixed action sequence, run in two
   independent processes; frame+RAM trajectory hashes must match.
3. Write the breakpoint (PASS or FAIL) and append it to the MMR ledger.

Run on the machine that will play the counted games. Each run appends a new breakpoint.
"""
from __future__ import annotations

import hashlib
import json
import multiprocessing as mp
import sys
from importlib.metadata import PackageNotFoundError, distribution
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.breakpoints import atom_record, create_breakpoint  # noqa: E402
from src.envcfg import ENV_CONFIG, make_env, runtime_versions  # noqa: E402
from src.fmo import fmo_root, leaf, sha256_file  # noqa: E402

OUT = ROOT / "evidence" / "runtime_v2"
PACKAGES = ["ale-py", "gymnasium", "numpy", "cloudpickle", "farama-notifications",
            "typing-extensions", "typesafe-sdk", "system-one-adapter"]
SEEDS = [1, 2, 3, 4, 5]
SMOKE_STEPS = 100


def hash_distribution(name: str):
    try:
        dist = distribution(name)
    except PackageNotFoundError:
        return None, []
    rows = []
    for f in dist.files or []:
        s = str(f)
        if "__pycache__" in s or s.endswith(".pyc"):
            continue
        if ".dist-info/" in s and not s.endswith(("METADATA", "WHEEL")):
            continue  # installer-specific (RECORD, INSTALLER, direct_url.json)
        p = Path(dist.locate_file(f))
        if not p.is_file():
            continue
        sha, n = sha256_file(p)
        rows.append({"path": f"{dist.metadata['Name']}=={dist.version}/{s}", "bytes": n, "sha256": sha})
    return dist.version, sorted(rows, key=lambda r: r["path"])


def build_runtime_dataset() -> dict:
    import ale_py.roms as roms

    groups, packages, leaves_out = {}, {}, []
    for name in PACKAGES:
        ver, rows = hash_distribution(name)
        if ver is None:
            packages[name] = {"state": "NOT_INSTALLED"}
            continue
        g = name
        groups[g] = [(r["path"], leaf(r["path"], r["bytes"], r["sha256"])) for r in rows]
        packages[name] = {"version": ver, "file_count": len(rows), "state": "HASHED_INSTALLED_FILES"}
        leaves_out += [{"group": g, **r} for r in rows]

    rom = Path(roms.get_rom_path("space_invaders"))
    rom_bytes = rom.read_bytes()
    rom_rec = {"path": "rom/space_invaders.bin", "bytes": len(rom_bytes),
               "sha256": hashlib.sha256(rom_bytes).hexdigest(),
               "md5": hashlib.md5(rom_bytes).hexdigest(), "source": "bundled in ale-py wheel"}
    groups["rom"] = [(rom_rec["path"], leaf(rom_rec["path"], rom_rec["bytes"], rom_rec["sha256"]))]
    leaves_out.append({"group": "rom", **{k: rom_rec[k] for k in ("path", "bytes", "sha256")}})

    exe = Path(sys.executable).resolve()
    esha, en = sha256_file(exe)
    groups["interpreter"] = [("interpreter/python", leaf("interpreter/python", en, esha))]
    leaves_out.append({"group": "interpreter", "path": "interpreter/python", "bytes": en, "sha256": esha})

    root, group_roots = fmo_root(groups)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "RUNTIME_LEAVES.jsonl").write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in leaves_out))
    manifest = {
        "schema": "VITHIA_RUNTIME_SOURCE_DATASET_V2",
        "dataset_id": "VITHIA_SPACE_RUNTIME_SOURCE_V2",
        "supersedes": "VITHIA_SPACE_RUNTIME_SOURCE_FREEZE_20260927_001",
        "supersede_reason": "Pilot runtime is ALE/SpaceInvaders-v5 via ale-py, which bundles the ROM; "
                            "the PettingZoo/multi-agent-ALE freeze recorded ROM=NOT_PRESENT.",
        "classification": "EXECUTABLE_EVIDENCE_DATASET",
        "runtime": runtime_versions(),
        "env_config": ENV_CONFIG,
        "packages": packages,
        "rom": rom_rec,
        "leaves_file": "evidence/runtime_v2/RUNTIME_LEAVES.jsonl",
        "fmo": {"root": root, "groups": group_roots, "leaf_count": len(leaves_out)},
        "unknowns": ["NATIVE_BUILD_PROVENANCE: NOT_VERIFIED",
                     "TRANSITIVE_LICENSE_REVIEW: PARTIAL",
                     "INTERPRETER_BUILD_PROVENANCE: NOT_VERIFIED"],
        "claim_ceiling": "IDENTITY_OF_INSTALLED_BYTES_ON_THIS_MACHINE",
    }
    (OUT / "RUNTIME_SOURCE_DATASET_V2.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def trajectory_hash(seed: int) -> dict:
    env = make_env()
    obs, info = env.reset(seed=seed)
    h = hashlib.sha256()
    first = hashlib.sha256(obs.tobytes()).hexdigest()
    for t in range(SMOKE_STEPS):
        a = (7 * t + seed) % 6
        obs, r, term, trunc, info = env.step(a)
        ram = env.unwrapped.ale.getRAM().tobytes()
        h.update(obs.tobytes() + ram + str((float(r), info["lives"], term, trunc)).encode())
        if term or trunc:
            break
    env.close()
    return {"seed": seed, "first_obs_sha256": first, "trajectory_sha256": h.hexdigest(),
            "steps": t + 1, "episode_frame_number": int(info["episode_frame_number"])}


def run_pass() -> list[dict]:
    ctx = mp.get_context("spawn")  # fresh interpreter: no shared emulator state
    with ctx.Pool(1) as pool:
        return pool.map(trajectory_hash, SEEDS)


def smoke() -> dict:
    a, b = run_pass(), run_pass()
    rows = [{**x, "trajectory_sha256_run_b": y["trajectory_sha256"],
             "match": x["trajectory_sha256"] == y["trajectory_sha256"]
             and x["first_obs_sha256"] == y["first_obs_sha256"]} for x, y in zip(a, b)]
    res = {"schema": "VITHIA_ENV_DETERMINISM_SMOKE_V1", "env_config": ENV_CONFIG,
           "runtime": runtime_versions(), "steps_per_seed": SMOKE_STEPS,
           "action_rule": "a_t = (7*t + seed) mod 6", "hashed_per_step": "rgb obs bytes + RAM + (reward, lives, terminated, truncated)",
           "runs": rows, "gate": "PASS" if all(r["match"] for r in rows) else "FAIL"}
    (OUT / "SMOKE_DETERMINISM.json").write_text(json.dumps(res, indent=2) + "\n")
    return res


def main() -> int:
    manifest = build_runtime_dataset()
    print(f"RUNTIME_FMO_ROOT={manifest['fmo']['root']}  LEAVES={manifest['fmo']['leaf_count']}")
    res = smoke()
    print(f"DETERMINISM_GATE={res['gate']}")
    atoms = [atom_record("evidence/runtime_v2/RUNTIME_SOURCE_DATASET_V2.json", "RuntimeSourceDatasetFCO", "runtime"),
             atom_record("evidence/runtime_v2/RUNTIME_LEAVES.jsonl", "RuntimeLeavesFCO", "runtime"),
             atom_record("evidence/runtime_v2/SMOKE_DETERMINISM.json", "EnvSmokeReceiptFCO", "smoke"),
             atom_record("scripts/bp_runtime.py", "CodeFCO", "code"),
             atom_record("src/envcfg.py", "CodeFCO", "code"),
             atom_record("src/fmo.py", "CodeFCO", "code"),
             atom_record("src/breakpoints.py", "CodeFCO", "code")]
    entry = ROOT / "evidence/entry/ENTRY_RECEIPT_001.json"
    if entry.exists():
        atoms.append(atom_record("evidence/entry/ENTRY_RECEIPT_001.json", "EntryReceiptFCO", "entry"))
    state = "ROM_BOUND_RUNTIME_PASS" if res["gate"] == "PASS" else "ROM_BOUND_RUNTIME_FAIL"
    out = create_breakpoint("rom-bound-runtime", state, atoms, {
        "runtime_fmo_root": manifest["fmo"]["root"],
        "rom_sha256": manifest["rom"]["sha256"], "rom_md5": manifest["rom"]["md5"],
        "fcg_edges": [
            {"src": "RuntimeSourceDataset_V2", "rel": "SUPERSEDES", "dst": "VITHIA_SPACE_RUNTIME_SOURCE_FREEZE_20260927_001"},
            {"src": "EnvSmokeReceipt", "rel": "EXECUTED_WITH", "dst": "RuntimeSourceDataset_V2"},
            {"src": "EntryReceipt_001", "rel": "REFERENCES", "dst": "repo:biobitworks/jev-space-invaders"}],
        "executed": ["hashed installed runtime files", "hashed bundled ROM", "determinism smoke x2 (spawned processes)"],
        "observed": {"determinism_gate": res["gate"], "seeds": SEEDS},
        "not_tested": ["JEV", "LLM baseline", "full episodes"],
        "next_action": "harness breakpoint: record_run() auto-push; scripted-policy games"})
    print(json.dumps({k: out[k] for k in ("bp_id", "bp_file", "bp_root", "mmr_size", "mmr_root_after")}, indent=2))
    return 0 if res["gate"] == "PASS" else 3


if __name__ == "__main__":
    raise SystemExit(main())
