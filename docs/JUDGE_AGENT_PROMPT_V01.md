# Judge Agent Prompt — Vithia-Space Independent Reproducibility V01

Use this prompt with your preferred coding/terminal agent. It needs no developer-owned credential and no write access to the repository.

---

You are independently verifying the post-submission Vithia-Space reproducibility successor.

Repository: https://github.com/biobitworks/jev-space-invaders
Target branch: postsubmission/judge-reproducibility-v02 (pull request #9)

Do not modify or reinterpret historical competition evidence. Everything you produce is your own local receipt; do not push anything.

Prerequisites (install only what is missing; do not download any model):
- git, and Python 3.10+ available as `python3`
- Python package `cryptography`
- Gum (https://github.com/charmbracelet/gum) only if you run the interactive UI in step 8
- Optional: Ollama with already-installed local models

Setup:

```bash
GIT_LFS_SKIP_SMUDGE=1 git clone --branch postsubmission/judge-reproducibility-v02 https://github.com/biobitworks/jev-space-invaders.git
cd jev-space-invaders
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -r live_demo/requirements.txt cryptography
```

Your task:

1. Report the exact branch, HEAD (`git rev-parse HEAD`), origin parity, and worktree state.

2. Verify the frozen Seed FCO and source:
   - file: evidence/fcg_seeds/UFA_JEV_SUBMITTED_PLAYTHROUGH_240_V1.seed.json
   - expected root: sha256:45d04e0d2da5f0c1255844b011bb2576320e1ff5517f0e38d8e79b8899a88bc8
   - expected submitted source commit: 4c943a92e84d0fb2cd3d01e4fdf15a10991eda71

3. Discover the machine's actual local inference surfaces before choosing a model:
   - Ollama binary/version, and `http://127.0.0.1:11434/api/tags`
   - `python3 -m live_demo.probe_integrations`
   - OpenJEV only through `python3 scripts/openjev_runtime.py status` (a `FileNotFoundError` for its state file means NOT_RUNNING)
   Do not guess service identity from an open port. Do not download a missing model.

4. Inventory usable LOCAL text models. Exclude embedding-only and cloud-only models. Do not exclude a family merely because it is Qwen3, reasoning-oriented, Liquid, small, or different from another machine.

5. Run the discovery-driven verification, which puts every discovered local model plus a scripted reference lane through Vithia preprocessing -> ONE shared verified context -> decider -> claim gate -> outcome, with no git writes:

   ```bash
   python3 tools/verify_doctor3_ollama_local.py --auto-lanes --local-only
   ```

   If no local model exists it runs the scripted lane only and says so. Report that; do not substitute a downloaded model.

6. Do not silently fall back. If a requested provider or model is unavailable, report BLOCKED / NOT_AVAILABLE / NOT_EXECUTED exactly.

7. Preserve model decisions exactly. If a model claims more than the Vithia context supports, do not tune or rewrite it; confirm that the unsupported action was blocked rather than executed (`LANES_CLAIM_GATE_INTEGRITY=PASS`).

8. Optionally run the interactive Doctor3 UI (no commit, no push):

   ```bash
   bash tools/vithia_doctor3.sh --seed-fco evidence/fcg_seeds/UFA_JEV_SUBMITTED_PLAYTHROUGH_240_V1.seed.json --local-only
   ```

   Generate a new local Ed25519 identity (or choose anonymous), skip sponsor credentials, and choose a decider. The "local Ollama" choice uses `OLLAMA_MODEL` (default `llama3.2:3b`) and is BLOCKED if that model is not installed.

9. Independently verify the frozen custody objects:

   ```bash
   python3 scripts/verify_final_playthrough_custody_v2.py evidence/competition/final_execution/frames
   python3 scripts/verify_e2e_breakpoints.py
   python3 scripts/secret_scan.py
   ```

   Note: `python3 scripts/verify_competition_lineage.py` reports `ATOM_CHANGED` on this branch (and on the submitted commit and `main`) because `README.md` and some `demo/` files changed after their atoms were frozen. Report the exact output; do not treat it as PASS and do not edit history. See docs/JUDGE_REPRODUCIBILITY_UPDATE_V01.md.

10. If you hold an authorized TypeSafe JEV key you may additionally test the hosted path with `TYPESAFE_API_KEY` set in the process environment only (command in the update document). Without a key, hosted JEV must remain NOT_EXECUTED / BLOCKED and no local backend may be relabeled as JEV.

11. Never expose or commit credentials, private signing keys (they live in `~/.vithia/identities/`, outside git), tokens, ROMs, private files, or unrelated proprietary material.

12. Return a concise receipt:

```text
HOST=
BRANCH=
HEAD=
ORIGIN_PARITY=
WORKTREE=

SEED_FCO_VERIFY=
SEED_ROOT=
SEED_ROOT_MATCH=
SOURCE_COMMIT=
SOURCE_PIN=

LOCAL_RUNTIME_INVENTORY=
LOCAL_MODELS_AVAILABLE=
LANES_SELECTED=

VITHIA_PREPROCESSING=
VERIFIED_CONTEXT_ROOT=
CONTEXT_CEILING=
SAME_INPUT_CONTEXT_ROOT_ACROSS_LANES=

(per lane)
LANE=
PROVIDER=
MODEL=
DECISION_ACTION=
DECISION_SUPPORTED_BY_CONTEXT=
ACTION_EXECUTION=
OUTCOME=

LANES_CLAIM_GATE_INTEGRITY=
PARENT_CHAIN_VERIFY=
FINAL_FCG_BP_VERIFY=
FINAL_FCG_ROOT=

CHECKPOINT_SIGNATURE_STATE=
CHECKPOINT_SIGNATURE_VERIFY=

PLAYTHROUGH_VERIFY=
COMPETITION_LINEAGE=
SECRET_SCAN=

HOSTED_JEV=
OPENJEV=

BLOCKED=
NOTES=
```

Do not convert a negative or unavailable state to PASS. Hash/Merkle/MMR verification establishes declared byte/order/custody integrity, not scientific truth.
