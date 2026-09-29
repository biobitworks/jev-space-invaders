# Judge Agent Prompt — Vithia-Space Independent Reproducibility V01

Use this prompt with your preferred coding/terminal agent while working in the public repository.

---

You are independently verifying the post-submission Vithia-Space reproducibility successor.

Repository:
https://github.com/biobitworks/jev-space-invaders

Target branch:
postsubmission/judge-reproducibility-v01

Do not modify or reinterpret historical competition evidence.

Your task is:

1. Clone or update the target branch and report the exact branch, HEAD, origin parity, and worktree state.

2. Verify the frozen Seed FCO:
   - file: evidence/fcg_seeds/UFA_JEV_SUBMITTED_PLAYTHROUGH_240_V1.seed.json
   - expected root:
     sha256:45d04e0d2da5f0c1255844b011bb2576320e1ff5517f0e38d8e79b8899a88bc8
   - expected submitted source commit:
     4c943a92e84d0fb2cd3d01e4fdf15a10991eda71

3. Discover the machine's actual local inference surfaces before choosing a model.
   Check:
   - Ollama binary/version
   - http://127.0.0.1:11434/api/tags
   - live_demo.probe_integrations
   - OpenJEV only through scripts/openjev_runtime.py status
   Do not guess service identity from an open port.
   Do not download a missing model merely to imitate another machine.

4. Inventory usable LOCAL text models.
   Exclude embedding-only and cloud-only models.
   Do not exclude a family merely because it is Qwen3, reasoning-oriented, Liquid, small, or otherwise different from a previous machine.

5. Run at least one actually available local model through:
   Vithia preprocessing -> verified context -> decider -> claim gate -> outcome.

6. Do not silently fall back.
   If a requested provider/model is unavailable, report BLOCKED / NOT_AVAILABLE / NOT_EXECUTED exactly.

7. Preserve model decisions exactly.
   If a model overclaims relative to the Vithia context ceiling, do not tune or rewrite it.
   Confirm that the unsupported action is blocked rather than executed.

8. Run the Doctor3 FCG path:
   bash tools/vithia_doctor3.sh --seed-fco evidence/fcg_seeds/UFA_JEV_SUBMITTED_PLAYTHROUGH_240_V1.seed.json

   For an independent signed run:
   - generate a new local Ed25519 identity;
   - skip sponsor credentials unless you are explicitly providing your own;
   - choose a local decider actually available on your machine.

9. Verify:
   - seed/root;
   - source pin;
   - Vithia preprocessing;
   - parent chain;
   - final FCG breakpoint;
   - checkpoint signature if signing is used;
   - secret scan.

10. If you have an authorized TypeSafe JEV key, you may additionally test the hosted JEV path by setting TYPESAFE_API_KEY in the process environment only.
    If no key is present, hosted JEV must remain NOT_EXECUTED / BLOCKED and no local backend may be relabeled as JEV.

11. Never expose or commit credentials, private signing keys, tokens, ROMs, private files, or unrelated proprietary material.

12. Return a concise receipt containing:

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
MODEL_SELECTED=
DECIDER_PROVIDER=

VITHIA_PREPROCESSING=
VERIFIED_CONTEXT_ROOT=
CONTEXT_CEILING=

DECISION_ACTION=
DECISION_SUPPORTED_BY_CONTEXT=
ACTION_EXECUTION=
OUTCOME=

PARENT_CHAIN_VERIFY=
FINAL_FCG_BP_VERIFY=
FINAL_FCG_ROOT=

CHECKPOINT_SIGNATURE_STATE=
CHECKPOINT_SIGNATURE_VERIFY=

SECRET_SCAN=

HOSTED_JEV=
OPENJEV=

BLOCKED=
NOTES=

Do not convert a negative or unavailable state to PASS. Hash/Merkle/MMR verification establishes declared byte/order/custody integrity, not scientific truth.
