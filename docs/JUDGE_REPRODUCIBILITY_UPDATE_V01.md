# Vithia-Space — Post-Submission Judge Reproducibility Update V01

> This document is a post-submission reproducibility successor. It does **not** replace or rewrite the accepted UFA entry, the qualified competition lineage, the submitted gameplay, or any historical breakpoint.

## Canonical identity

- Repository: `biobitworks/jev-space-invaders`
- Successor branch: `postsubmission/judge-reproducibility-v01`
- Packaging predecessor: `postsubmission/vithia-doctor3-v01`
- Packaging predecessor HEAD: `81c181a61bb8469dbef60836b9939da434d41264`
- Frozen submitted source commit: `4c943a92e84d0fb2cd3d01e4fdf15a10991eda71`
- Frozen Seed FCO root: `sha256:45d04e0d2da5f0c1255844b011bb2576320e1ff5517f0e38d8e79b8899a88bc8`

Hashes and Merkle/MMR commitments establish byte identity, ordered custody, and reconstruction of the declared objects. They do not by themselves establish scientific correctness or semantic equivalence.

## What judges can verify without sponsor credentials

The repository now exposes a fail-closed Vithia/Doctor3 path with:

- exact Seed FCO verification and source pinning;
- Vithia preprocessing and verified-context construction;
- local decider adapters;
- lane-specific Decision/Action/Outcome FCOs;
- claim-gate enforcement;
- append-only Merkle/MMR checkpoints;
- optional local Ed25519 checkpoint signing;
- secret scanning;
- no silent fallback when a requested provider is unavailable.

The local path does **not** require Mitosis, Tenki, TypeSafe/JEV, Anthropic, OpenAI, or AWS credentials. If one of those providers is not configured, the corresponding state remains BLOCKED / NOT_AVAILABLE / NOT_EXECUTED rather than being normalized to PASS.

## Existing evidence

The post-submission successor contains:

- a real Doctor3 seed-to-final-root run with Mitosis and Tenki in an earlier headless session;
- signed three-breakpoint FCG sessions;
- local Ollama rehearsals;
- a shared-Vithia-context multi-lane rehearsal in which unsupported model claims were preserved in DecisionFCOs and blocked from execution;
- bounded local OpenJEV engineering evidence in the repository's existing OpenJEV lane;
- a public live-demo path and replay/custody evidence.

The strict claims of each historical session remain whatever its receipt recorded. This update does not upgrade a FAIL, PARTIAL, BLOCKED, UNKNOWN, NOT_EXECUTED, or NOT_COMPARABLE state.

## MagicStudio portability preflight

A fresh clone on MagicStudio independently verified:

- branch/origin parity;
- clean worktree;
- exact Seed FCO root;
- exact submitted source commit;
- local Ollama daemon reachability;
- Doctor3 Ollama adapter wiring.

That particular requested model matrix was intentionally stopped because the exact requested models were not installed in that Ollama daemon. At that observation, the daemon exposed only `longhorizon-liquid-230m:latest` and `qwen2.5:0.5b`. The stop is preserved as an environment-discovery result, not converted into a portability PASS.

Judges should therefore discover their own local models first rather than relying on model names from another machine.

## Judge path A — no external API key

From a clean clone:

```bash
git clone https://github.com/biobitworks/jev-space-invaders.git
cd jev-space-invaders
git fetch origin
git checkout postsubmission/judge-reproducibility-v01

python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r live_demo/requirements.txt

python -m live_demo.probe_integrations
ollama list
```

Choose one actually installed local text model reported by the probe / Ollama inventory, then run:

```bash
python -m live_demo.run   --mode 1p   --seed 3   --steps 3   --player0-preprocessor vithia   --player0-decider ollama:<EXACT_DISCOVERED_MODEL>   --headless
```

Do not substitute a different backend if the requested model is unavailable. Report the blocker.

For the FCG/Doctor3 path:

```bash
bash tools/vithia_doctor3.sh   --seed-fco evidence/fcg_seeds/UFA_JEV_SUBMITTED_PLAYTHROUGH_240_V1.seed.json
```

Recommended interactive choices for an independent verification are:

- generate a new local Ed25519 identity;
- skip sponsor credentials unless the judge chooses to provide their own;
- select a local decider that the machine actually exposes.

The private signing key stays outside Git. Only the public key/fingerprint and signature enter evidence.

## Judge path B — hosted TypeSafe JEV with judge-provided key

Hosted JEV is intentionally fail-closed. If the judge has an authorized TypeSafe key:

```bash
export TYPESAFE_API_KEY=<judge-provided-key>

python -m live_demo.run   --mode 1p   --preprocessor vithia   --decider jev   --render terminal   --headless   --run-class COMPETITION_JEV
```

If `TYPESAFE_API_KEY` is absent, the runner must report the missing-key blocker and must not silently relabel OpenJEV, Ollama, Tenki, Mitosis, or another backend as hosted JEV.

## OpenJEV

Do not guess an OpenJEV port.

Use:

```bash
python3 scripts/openjev_runtime.py status
```

If an existing verified runtime is not resident, record `OPENJEV=NOT_RUNNING` / `NOT_AVAILABLE`. If the already-defined local runtime is present, use `scripts/openjev_runtime.py serve` and the authoritative endpoint it records. Do not infer service identity merely from a listening loopback port.

## What a successful independent verification should establish

A successful local verification can establish:

```text
SEED_FCO_VERIFY=PASS
SEED_ROOT_MATCH=PASS
SOURCE_PIN=PASS
VITHIA_PREPROCESSING=PASS
PARENT_CHAIN_VERIFY=PASS
FINAL_FCG_BP_VERIFY=PASS
SECRET_SCAN=PASS
```

If a generated local Ed25519 identity is used:

```text
CHECKPOINT_SIGNATURE_STATE=PASS
CHECKPOINT_SIGNATURE_VERIFY=PASS
```

If a model selects a claim above the Vithia evidence ceiling, that model decision is preserved and the expected safe result is:

```text
DECISION_SUPPORTED_BY_CONTEXT=NO
ACTION_EXECUTION=BLOCKED
OUTCOME=BLOCKED
```

That is an intended claim-gate result, not a reason to rewrite or tune the model output.

## Submission boundary

This GitHub update is ready for judge review as post-submission reproducibility evidence.

It is **not** proof that the organizer API accepts a later POST as an update to the accepted entry. Repository evidence records the organizer update/upsert semantics as `NOT_VERIFIED`. Therefore no automated resubmission should be sent merely because a POST collection endpoint exists.

The accepted submission remains unchanged unless an organizer-facing UI, instruction, or verified API contract explicitly authorizes an update.
