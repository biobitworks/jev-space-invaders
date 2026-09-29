# Vithia Space Live Demo

This is a local-only browser control room for the real ALE `SpaceInvaders-v5`
environment and the real PettingZoo `space_invaders_v2` environment. Each
player is a `PlayerSeatConfig` with an independent preprocessor and decider.
Inference happens outside the control lock; pause, stop, reset, and seat
changes invalidate the current generation and late results are discarded.

## Clean clone

Derive the repository address from the checkout:

```sh
git remote get-url origin
git clone <the-value-returned-above>
cd <repo-directory>
git fetch --all
git checkout competition/final-integration-v01
```

## Python and dependencies

Use Python 3.12 or newer with a virtual environment:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r live_demo/requirements.txt
```

The canonical repository also contains its existing project requirements.
The 2P environment needs a legal Space Invaders ROM. Do not commit ROMs,
weights, caches, credentials, or `entry.local.json`.

## Local runtimes

- ALE: `ale-py` and Gymnasium, using the existing `src.envcfg.make_env`.
- PettingZoo: `pettingzoo` and `multi-agent-ale-py`; set `ALE_ROM_DIR` to a
  directory containing `space_invaders.bin`.
- Ollama: `OLLAMA_BASE_URL`, with models discovered from `/api/tags`.
- OpenJEV: `OPENJEV_BASE_URL`; the local System-One interface is selected as
  `SYSTEM_ONE / OPENJEV_LOCAL` only when the verified runtime is resident.
- Liquid local: `LIQUID_LOCAL_URL` and an exact discovered model.
- Optional JEV API, Tenki, Mitosis, and Liquid API variables are listed in
  `live_demo/.env.example`. Variable names only are committed.

## Terminal-first runner

The authoritative execution path is the Python CLI. It runs the real
Gymnasium/ALE 1P environment, can use the PettingZoo 2P environment when ROM
access is available, prints terminal telemetry, writes a thin FCO/FCG trace,
and appends a canonical `terminal_runs` row to `results.json`.

```sh
python -m live_demo.run --mode 1p --seed 3 --steps 3 \
  --player0-preprocessor vithia \
  --player0-decider ollama:qwen2.5:0.5b \
  --headless
```

Fast deterministic smoke:

```sh
python -m live_demo.run --mode 1p --seed 3 --steps 1 \
  --player0-preprocessor none \
  --player0-decider scripted \
  --run-class SCRIPTED_CONTROL \
  --headless
```

2P, when `ALE_ROM_DIR` points to the legal Space Invaders ROM directory:

```sh
python -m live_demo.run --mode 2p --seed 3 --steps 1 \
  --player0-preprocessor vithia --player0-decider scripted \
  --player1-preprocessor vithia --player1-decider liquid:longhorizon-liquid-230m:latest \
  --headless
```

`OPENJEV_LOCAL` is reported as engineering-only unless its guarded runtime is
resident. `JEV_API_REMOTE` is blocked unless `TYPESAFE_API_KEY` is present.
Ollama and Liquid local runs are never labeled as official TypeSafe JEV runs.

## Replay seed and verification

For an existing run bundle:

```sh
python -m live_demo.run \
  --replay-seed-run-dir evidence/competition/openjev_ab/run_openjev_vithia_l1_2701834b043f \
  --breakpoint-id ENGINEERING-OPENJEV-VITHIA-L1

python -m live_demo.run \
  --verify-replay-seed evidence/competition/openjev_ab/run_openjev_vithia_l1_2701834b043f/REPLAY_SEED_FCO.json
```

`REPLAY_SEED_FCO` is reconstructive metadata: it references content-addressed
manifests, actions, FCO streams, frame indexes, state snapshots, and MMR roots.
The MMR root authenticates ordered bytes; it is not itself the replay data.
Random access is reported separately from proof and full replay.

## Optional browser launch

```sh
python -m live_demo.probe_integrations
python -m live_demo.server --port 8788
```

Open `http://127.0.0.1:8788`.

The browser is optional showmanship/control-room surface. It is not required
for terminal E2E acceptance.

Seat-specific browser automation uses JSON:

```sh
curl -s -X POST http://127.0.0.1:8788/api/seat/PLAYER_0 \
  -H 'content-type: application/json' \
  -d '{"preprocessor":"VITHIA_SPACE","decision_layer":"SYSTEM_ONE","decider_provider":"OLLAMA","decider_backend":"qwen2.5:0.5b","exact_model":"qwen2.5:0.5b"}'
```

Use `/api/seat/PLAYER_1` for 2P. Use `/api/mode`, `/api/play`, `/api/pause`,
`/api/stop`, `/api/reset`, and `/api/step` for lifecycle control.

For 1P, counted actions use the strict six-class ECA bijection
`MOVE={NONE,LEFT,RIGHT} x FIRE={NO,YES}` ->
`NOOP,FIRE,LEFT,LEFTFIRE,RIGHT,RIGHTFIRE`. `NOOP` executes a real
no-move/no-fire ALE step; PAUSE and STOP execute no environment step and are
lifecycle states, not ECA actions.

## Provider and preprocessor diagnostics

`python -m live_demo.probe_integrations` reports discovered/configured/
authenticated/reachable/inference-tested/gameplay-capable fields. A provider
is not marked PASS merely because a historical receipt exists. `VITHIA_SPACE`
means `perception_v1` / `A5 / VITA01_FULL_PUBLIC`; it provides context only and
never selects the counted action. `NONE` is an explicit no-preprocessor path.

The useful acceptance pairs are Vithia/OpenJEV, None/OpenJEV, Vithia/Ollama,
Vithia/Liquid Local, and mixed 2P seats, but only cells actually executed with
a resident backend can be reported PASS. Tenki and Mitosis are blocked or
context-only when their current runtime contract is unavailable.

## Troubleshooting

- Missing model: inspect `/api/models` and the provider registry.
- Bad credential: the provider remains `BLOCKED`; no fallback is silently
  relabeled as the requested backend.
- ROM blocked: set `ALE_ROM_DIR` to the legal ROM directory.
- OpenJEV not resident: run the repository's guarded OpenJEV runtime tooling;
  do not download duplicate weights.
- Ollama down: the seat records a fail-closed fallback and the integration is
  not marked live.
- Port conflict: start with another `--port` and use that URL.

See also: [HOWTO_INDEPENDENT_STARTUP.md](HOWTO_INDEPENDENT_STARTUP.md) (script-based independent startup and judge path).
