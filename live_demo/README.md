# Vithia-Space Live Gameplay Demo

State: implementation branch only. No competition breakpoint is allocated by
this package. No live run becomes canonical until an operator reviews the
result and explicitly admits a successor.

## Purpose

This package provides the missing judge-visible execution surface:

- actual live ALE/SpaceInvaders-v5 gameplay;
- selectable local model backend discovered from Ollama;
- optional Vithia-Space public A5/Vita01 preprocessing;
- Play / Pause / Stop / Reset / Step Once;
- Tetris-style actual-history vs model-projected action queue;
- right-side decision stream;
- 1P and explicit ROM-gated PettingZoo 2P;
- receipt-backed Mitosis/Tenki/OpenJEV/Liquid/Vithia integration status;
- fail-closed acceptance and final-submission scripts.

It is not the historical 4-second custody replay.

## Canonical predecessor

This branch was created from:

```
competition/final-integration-v01
e5fab430b4b0e534ab469994f6ba60dd60b15818
UFA-JEV-COMP-BP-0016
MMR size 16
MMR root d5a34bcc5da38cb7a758c0af8e8e8708a6d7bfb7af9266b9f7181b54246999c4
```

Always fetch before integrating. If the competition branch has advanced,
rebase/cherry-pick this implementation as a successor; never rewrite the
historical breakpoint atoms.

## Pull on magicSTUDIO

```bash
cd /Users/byron/projects/active/jev-space-invaders
git fetch origin --prune
git worktree add \
  /Users/byron/projects/active/vithia-space-live-demo \
  origin/feature/vita01-live-gameplay-demo-v01

cd /Users/byron/projects/active/vithia-space-live-demo
python -m live_demo.probe_integrations
python -m live_demo.server --port 8788
```

Then open:

```
http://127.0.0.1:8788
```

The server binds loopback only.

## 1P

1P reuses the competition substrate:

```
src/envcfg.py
src/perception.py
src/actions.py
```

The visible browser frame is the actual current ALE RGB observation. A selected
controller receives only the compact perception state plus optional public
Vita01 context.

The public Vithia-Space preprocessor is:

```
A5_VITA01_FULL_PUBLIC =
state
+ bounded actual history
+ Anticube classification
+ public path_distribution
```

It is a preprocessor. The selected backend model still makes the action.

Private System-0 / private DeltaG* is not used.

## Models

The UI queries the live Ollama API rather than hardcoding models.

At an earlier magicSTUDIO observation, the available models were:

```
longhorizon-liquid-230m:latest
qwen2.5:0.5b
```

Those are observations, not guaranteed future state.

`SCRIPTED_BASELINE` is available but clearly labeled NON_MODEL_REFERENCE.

`OPENJEV_TARGETED_EXPLORATORY` is disabled unless
`OPENJEV_TARGETED_BASE_URL` is explicitly configured. It is always labeled:

```
OPEN SOURCE JEV STAND-IN
EXPLORATORY
NON_TYPESAFE_JEV
NON_COUNTED
NONCOMPARABLE
```

It does not repair or replace the historical matched-comparator result.

## 2P

2P uses the existing separate PettingZoo action ontology:

```
NOOP FIRE UP RIGHT LEFT DOWN
```

Do not reuse ALE action IDs.

The lane remains fail-closed unless the operator supplies an explicitly
authorized ROM directory:

```bash
export VITHIA_2P_ROM_DIR=/authorized/path/holding/space_invaders.bin
```

The existing `experiments/e5_2p.py::rom_gate` verifies presence and hashes the
bytes. This package does not acquire, download, copy, or bypass a ROM gate.

Install the already-declared optional environment if required:

```bash
python3.12 -m venv /Volumes/magicBLACKbox/vithia-space-execution/pettingzoo-2p-venv
source /Volumes/magicBLACKbox/vithia-space-execution/pettingzoo-2p-venv/bin/activate
pip install -r requirements-2p.txt
```

If the ROM remains unavailable, the browser must show `ROM_GATE_BLOCKED`.
That is not a 2P PASS.

## Action timeline

The center/right display separates:

```
EXECUTED HISTORY | NOW | MODEL-PROJECTED / NOT YET EXECUTED
-6 ... -1          0     +1 ... +6
```

Past actions are actual executed actions.

Projected actions are advisory model output only. They are recomputed after each
new observation and never represented as observed future states.

## Integration checks

Run:

```bash
python -m live_demo.probe_integrations
```

The probe distinguishes historical evidence from current availability.

### Mitosis Labs

Current repository evidence includes a final remember/retrieve receipt and a
returned universal ID. The public-safe probe does not perform a new Cortex
network mutation.

### Tenki

Earlier governed sandbox execution exists. The final competition receipt records
a later invalid/revoked-credential block. The probe reports current CLI and
credential presence without printing secrets.

A new live Tenki claim requires a fresh authorized Tenki check/receipt.

### OpenJEV

The historical matched lane remains
`NOT_TESTED_CAPABILITY_MISMATCH`.

A targeted exploratory endpoint may be used only under the explicit
noncomparable label above.

### Liquid AI

The browser lists any currently resident Ollama model by exact served name.
Names containing `liquid` are surfaced as local Liquid-family candidates;
that does not imply equivalence to another Liquid release or sponsor runtime.

### Vithia-Space

The A5 public preprocessor is available from the existing public experiment
code. The UI shows whether it is ON or RAW.

## Acceptance

With the server running:

```bash
python -m live_demo.acceptance
```

The acceptance runner requires:

- a real discovered Ollama model;
- 1P Step Once advances exactly once;
- 1P live Play advances;
- Pause freezes;
- a real RGB frame is returned;
- 2P execution PASS.

If 2P is explicitly still ROM-gated and the operator chooses not to make 2P a
submission gate, the bounded exception must be explicit:

```bash
python -m live_demo.acceptance --allow-2p-blocked
```

That produces `PASS_WITH_EXPLICIT_2P_BLOCK`, not a 2P success claim.

Default receipt:

```
/tmp/vithia-space-live-demo/ACCEPTANCE_RECEIPT.json
```

## Recording

Record the browser only after acceptance.

For the judge video, show:

1. 1P actual model play.
2. Model selector.
3. Vithia-Space preprocessor ON/OFF state.
4. action history and projected queue;
5. live decision stream;
6. integration panel;
7. 2P live play if the ROM gate is legitimately cleared.
8. score relative to the reference 270 local-Ollama baseline and historical
   scripted reference 325.

Do not call a replay live gameplay.

## Final submission

After:

- acceptance receipt passes;
- the operator records/uploads the final demo;
- a public HTTPS video URL is available;

run:

```bash
python -m live_demo.finalize_submission \
  --demo-video-url "https://PUBLIC-DEMO-URL"
```

By default the finalizer uses the conservative sponsor boolean policy
(`mitosis=false`, `tenki=false`) while preserving truthful narrative
evidence.

If the operator deliberately chooses receipt-backed final booleans:

```bash
python -m live_demo.finalize_submission \
  --demo-video-url "https://PUBLIC-DEMO-URL" \
  --sponsor-mode receipt-backed
```

The finalizer requires:

```
server response ok == true
missing_for_judging == [] or absent
```

and writes the private payload/response under `/tmp`, not Git.

Do not commit `entry.local.json`, tokens, private keys, or the private media
carrier implementation.

## Admission after successful test

Only after operator review should Codex:

1. recover the then-current canonical competition branch;
2. preserve this demo implementation as a successor;
3. create public-safe run/acceptance/video/submission receipts;
4. run secret/private-IP scans;
5. allocate the next available qualified breakpoint;
6. append it to the ordered MMR;
7. verify the new root;
8. push origin parity.

Do not allocate a breakpoint simply because this implementation branch exists.
