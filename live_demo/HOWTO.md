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

## Launch

```sh
python -m live_demo.probe_integrations
python -m live_demo.server --port 8788
```

Open `http://127.0.0.1:8788`.

The browser is optional. Seat-specific automation uses JSON:

```sh
curl -s -X POST http://127.0.0.1:8788/api/seat/PLAYER_0 \
  -H 'content-type: application/json' \
  -d '{"preprocessor":"VITHIA_SPACE","decision_layer":"SYSTEM_ONE","decider_provider":"OLLAMA","decider_backend":"qwen2.5:0.5b","exact_model":"qwen2.5:0.5b"}'
```

Use `/api/seat/PLAYER_1` for 2P. Use `/api/mode`, `/api/play`, `/api/pause`,
`/api/stop`, `/api/reset`, and `/api/step` for lifecycle control.

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
