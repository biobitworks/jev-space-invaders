# Codex Execution Handoff — Vithia-Space Live 1P/2P Demo

## Authority

Operator authorized this implementation branch to be committed/pushed so
magicSTUDIO can pull it. This is an implementation successor only; it is not a
qualified competition breakpoint and it does not mutate protected historical
atoms.

## Source state

Implementation branch:

```
feature/vita01-live-gameplay-demo-v01
```

Created from canonical competition predecessor:

```
competition/final-integration-v01
e5fab430b4b0e534ab469994f6ba60dd60b15818
UFA-JEV-COMP-BP-0016
MMR size 16
MMR root d5a34bcc5da38cb7a758c0af8e8e8708a6d7bfb7af9266b9f7181b54246999c4
```

Implementation parent before this handoff file:

```
d4c1216094af7366039c86f858f35c19667342d2
```

Always fetch and verify; do not assume these remain current.

## Pull without disturbing the active worktree

```bash
cd /Users/byron/projects/active/jev-space-invaders
git fetch origin --prune

git worktree add \
  /Users/byron/projects/active/vithia-space-live-demo \
  origin/feature/vita01-live-gameplay-demo-v01

cd /Users/byron/projects/active/vithia-space-live-demo
```

If the worktree already exists, verify it rather than recreating it.

## Phase A — discovery

Run:

```bash
git status --short --branch
git rev-parse HEAD
python -m live_demo.probe_integrations
curl -sS http://127.0.0.1:11434/api/tags
```

Check and report separately:

- Mitosis governed remember/retrieve receipt and universal ID.
- current Mitosis credential/tool availability, without exposing secrets.
- Tenki prior governed sandbox receipt.
- current Tenki CLI/credential/re-access state.
- OpenJEV matched comparator state.
- optional targeted OpenJEV demo capability.
- exact current Ollama model names.
- Liquid-family local model candidates by exact model name.
- Vithia-Space A5 public preprocessor import/state.
- 2P PettingZoo import.
- explicit ROM gate state.

Do not upgrade a historical claim because a credential exists.

## Phase B — launch live browser

Run:

```bash
python -m live_demo.server --port 8788
```

Open:

```
http://127.0.0.1:8788
```

The operator must see actual live game frames, not canonical.mp4.

## Phase C — 1P test

Required:

1. choose a real Ollama model;
2. enable A5_VITA01_FULL;
3. seed 3;
4. STEP ONCE;
5. verify exactly one live decision;
6. PLAY;
7. observe >=10 live model decisions;
8. verify changing RGB frames;
9. verify action stream;
10. verify executed backtrace;
11. verify projected queue;
12. PAUSE and confirm no step changes;
13. STEP ONCE while paused;
14. switch model and verify change is explicit;
15. resume;
16. STOP.

Record observed score. Do not predetermine success.

Reference only:

```
local Ollama historical baseline = 270
historical scripted reference = 325
```

## Phase D — OpenJEV targeted exploratory lane

Do not change the matched-comparator historical state.

If and only if the local targeted shim can be explicitly launched:

```
OPENJEV_TARGETED_EXPLORATORY
NON_TYPESAFE_JEV
NON_COUNTED
NONCOMPARABLE
```

Configure its endpoint through:

```bash
export OPENJEV_TARGETED_BASE_URL=http://127.0.0.1:<actual-port>
```

Restart the demo server so the dropdown enables the lane.

Run visible gameplay and record the observed score.

If it cannot execute, preserve:

```
CAPABILITY_GATED
```

Do not block the normal local model demo on OpenJEV.

## Phase E — 2P test

2P is implemented but remains license/source gated.

Do not acquire/copy/download a ROM automatically.

Verify:

```bash
python -c "import pettingzoo"
```

If the operator has an authorized ROM:

```bash
export VITHIA_2P_ROM_DIR=/authorized/path
```

The directory must contain:

```
space_invaders.bin
```

The existing rom_gate hashes it before use.

Then in the browser:

- select 2P;
- choose model A;
- choose model B;
- enable A5 preprocessor;
- RESET;
- STEP ONCE;
- PLAY;
- observe both seats making real decisions;
- verify separate action ontology:
  NOOP FIRE UP RIGHT LEFT DOWN;
- verify score streams;
- PAUSE;
- STEP ONCE;
- STOP.

If ROM remains unavailable, report:

```
2P_STATE=NOT_EXECUTED_ROM_GATE_BLOCKED
```

Never report 2P PASS from a mock.

## Phase F — automated acceptance

Default strict test:

```bash
python -m live_demo.acceptance
```

This requires real 1P and real 2P PASS.

If the operator explicitly decides the competition submission may proceed while
2P remains ROM-gated:

```bash
python -m live_demo.acceptance --allow-2p-blocked
```

That is:

```
PASS_WITH_EXPLICIT_2P_BLOCK
```

not a 2P success claim.

## Phase G — recording

After acceptance, leave the live browser running.

Record a 60–90 second operator demo that visibly includes:

- actual 1P model gameplay;
- selected exact model name;
- Vithia-Space A5 preprocessor;
- Play/Pause/Step/Stop;
- executed-history vs projected-future queue;
- decision stream;
- score/lives/step;
- Mitosis/Tenki/OpenJEV/Liquid/Vithia integration panel;
- live 2P if and only if the ROM gate was legitimately cleared.

A replay may be used only as a labeled custody inset.

## Phase H — public video URL

Upload the operator-approved recording to a public/accessible HTTPS host.

Preferred operator workflow:

```
YouTube → Unlisted
```

Verify the URL in a logged-out/incognito browser.

## Phase I — final submission

With the accepted live-demo receipt and public URL:

```bash
python -m live_demo.finalize_submission \
  --demo-video-url "https://PUBLIC-URL"
```

Default sponsor policy is conservative:

```
mitosis=false
tenki=false
```

Do not flip booleans merely because old receipts exist.

Only use:

```
--sponsor-mode receipt-backed
```

if the operator deliberately authorizes the exact resulting claim scope.

Final success requires:

```
ok=true
missing_for_judging=[]
```

Preserve the complete response.

## Phase J — canonical admission

Only after the operator has watched the UI and the test/record/submission has
succeeded:

1. recover the then-current canonical competition branch;
2. verify this implementation branch against it;
3. reconcile any concurrent commits;
4. do not modify protected historical atoms;
5. create new public-safe run receipts;
6. preserve 1P/2P/OpenJEV failures and negative states;
7. run tests;
8. run lineage verification;
9. run secret/private-key/private-IP scans;
10. allocate the next available UFA-JEV-COMP breakpoint;
11. append ordered MMR leaf/peaks/root;
12. independently verify;
13. commit/push;
14. require origin parity.

Do not preallocate a breakpoint number in this handoff.

## Final Codex return

Return:

```
SOURCE_BRANCH
SOURCE_HEAD
CANONICAL_PARENT_HEAD

LIVE_URL
SERVER_PID

MODELS_AVAILABLE
LIQUID_MODEL_STATE
VITHIA_PREPROCESSOR_STATE
OPENJEV_TARGETED_STATE

MITOSIS_STATE
MITOSIS_UNIVERSAL_ID
TENKI_PRIOR_RUNTIME_STATE
TENKI_CURRENT_ACCESS_STATE

ONE_PLAYER_TEST_STATE
ONE_PLAYER_MODEL
ONE_PLAYER_SCORE
ONE_PLAYER_STEPS

TWO_PLAYER_TEST_STATE
TWO_PLAYER_MODELS
TWO_PLAYER_SCORES
ROM_GATE_STATE

ACCEPTANCE_STATE
ACCEPTANCE_RECEIPT

VIDEO_RECORDING_STATE
PUBLIC_DEMO_URL

FINAL_SUBMISSION_STATE
SUBMISSION_OK
MISSING_FOR_JUDGING

CANONICAL_ADMISSION_STATE
NEW_BREAKPOINT_IF_ANY
NEW_MMR_SIZE_IF_ANY
NEW_MMR_ROOT_IF_ANY

FAILURES
NOT_TESTED
NEXT_ACTION
```
