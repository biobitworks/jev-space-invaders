# Independent Startup: UFA JEV Bake-Off 2026

This guide explains how to run the Space Invaders competition from a fresh clone.

## Prerequisites

- macOS/Linux with Python 3.10+
- Terminal access
- ~2 GB free disk space (for ROM cache and model downloads)
- OpenJEV running locally (optional, for local decider tests)
- API keys in environment for remote deciders (optional)

## Clone and Setup

```bash
# Clone
git clone https://github.com/biobitworks/jev-space-invaders.git
cd jev-space-invaders
git checkout competition/final-integration-v01

# Python environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy .env template (store any API keys here, NEVER in git)
cp .env.example .env
# Edit .env and add any needed credentials:
#   TYPESAFE_API_KEY     (for hosted TypeSafe JEV)
#   ANTHROPIC_API_KEY    (for Claude baseline)
#   OPENAI_API_KEY       (for GPT baseline)
```

## Quick Start: Run a Game

### 1. Scripted Baseline (No Model)
Deterministic policy; always returns LEFT/RIGHT alternating every 30 steps. Smoke test only.

```bash
python scripts/run_games.py --decider scripted --seeds 1 2 3 --dry-run --results /tmp/test_results.json
```

**Expected**: 3 games run, each appends to `/tmp/test_results.json`. Scores vary based on RNG. Latency ~0.002 ms (local deterministic policy).

### 2. Ollama Local Baseline
Requires: `ollama run llama3.2:3b` running on http://localhost:11434

```bash
# Terminal 1: Start Ollama service
ollama serve

# Terminal 2: Run games
python scripts/run_games.py --decider llm --provider ollama --model llama3.2:3b --seeds 1 2 3 --dry-run --results /tmp/test_results.json
```

**Expected**: Each game ~100–200 steps (game ends when ship dies or reward plateau). Latency: 200–500 ms per decision (network + inference). Scores typically 200–500 points.

### 3. OpenJEV Local (System-One Compatible)
Requires: OpenJEV running on http://127.0.0.1:3000

```bash
# Terminal 1: Start OpenJEV (see OpenJEV_LOCAL_SETUP below)
cd ~/path/to/openjev && python -m openjev.server

# Terminal 2: Run games
python scripts/run_games.py --decider openjev --base-url http://127.0.0.1:3000 --seeds 1 2 3
```

**Expected**: 5 fixed-seed games. Results appended to `results.json` and pushed to git (requires clean worktree, `origin` configured, push permission).

## OpenJEV Local Setup

OpenJEV is a local System-One-compatible implementation. It allows running the same decision interface as the hosted TypeSafe JEV API without a remote provider.

### Prerequisites for OpenJEV
- Python 3.10+
- ~500 MB for model cache
- MLX framework (Apple Silicon optimized) or fallback to CPU

### Install and Run

```bash
# 1. Clone OpenJEV (assuming you have it)
cd ~/path/to/openjev

# 2. Install
pip install -e .

# 3. Start server
python -m openjev.server --port 3000

# Server logs:
# INFO: Uvicorn running on http://127.0.0.1:3000
```

### Verify OpenJEV is Responding

```bash
curl -X POST http://127.0.0.1:3000/v1/systemone \
  -H "Content-Type: application/json" \
  -d '{
    "state": {"ship": {"x": 128}, "bombs": [], "shots": [], "step": 0},
    "model": "openjev",
    "questions": {
      "move": {
        "type": "choice",
        "instructions": "Pick a move.",
        "criteria": {"NOOP": "Stay"}
      }
    }
  }'

# Expected response:
# {"answers": {"move": {"choice": "NOOP", "confidence": 0.95, "probabilities": {...}}}, "model": "openjev"}
```

## Running Full Competition Suite

**Warning**: Git push is live. Ensure:
- Working on `competition/final-integration-v01` branch
- Worktree is clean
- Origin is configured with push permission

```bash
# Run 5 games each for all available deciders
python scripts/run_games.py --decider scripted --seeds 1 2 3 4 5

# Then run one more decider (e.g., Ollama baseline)
python scripts/run_games.py --decider llm --provider ollama --model llama3.2:3b --seeds 1 2 3 4 5 --note "Local Ollama baseline, seed 1-5"

# Results are pushed to git automatically after each game
```

## Remote Deciders

### TypeSafe JEV (Hosted)
```bash
export TYPESAFE_API_KEY="sk-..."
python scripts/run_games.py --decider jev --seeds 1 2 3 4 5
```

**Note**: As of 2026-09-28, hosted JEV was NOT_AVAILABLE. This may be enabled later.

### Claude (Anthropic)
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
python scripts/run_games.py --decider llm --provider anthropic --model claude-haiku-4-5 --seeds 1 2 3 4 5
```

### OpenAI (GPT)
```bash
export OPENAI_API_KEY="sk-..."
python scripts/run_games.py --decider llm --provider openai --model gpt-4-mini --seeds 1 2 3 4 5
```

## Architecture: Per-Seat Deciders (2P)

For two-player games (if the environment supports it):

```
PLAYER_0:
  ├─ PREPROCESSOR: NONE or VITHIA_SPACE (state parsing)
  └─ DECIDER: openjev OR ollama OR anthropic

PLAYER_1:
  ├─ PREPROCESSOR: independent from P0
  └─ DECIDER: independent from P0 (can be different model/provider)
```

Currently, Space Invaders is 1P only. Per-seat architecture is reserved for multi-player extensions.

## Vithia (State Preprocessor)

Vithia parses the RGB frame into compact JSON:

```json
{
  "ship": {"x": 128, "y": 205},
  "bombs": [{"x": 50, "y": 100}, ...],
  "shots": [{"x": 128, "y": 180}, ...],
  "aliens": [{"x": 100, "y": 50}, ...],
  "shields": [{"x": 80, "y": 160}, ...],
  "score": 420,
  "lives": 3,
  "step": 45
}
```

Vithia does NOT preselect actions. It only provides context. The decider makes the choice.

**Supported preprocessors**:
- `NONE`: Use raw RGB frame (not implemented for current deciders)
- `VITHIA_SPACE`: JSON state (default, implemented)

## Tenki and Mitosis (Experimental)

These are sponsor integrations for decision tracing and caching. Both are currently **NOT_TESTED**:

- **Tenki**: Remote tracing/caching from a sponsor system. Last successful run: BP-0007. Current status: `BLOCKED_INVALID_OR_REVOKED_API_KEY`.
- **Mitosis**: Universal-ID-backed directive for seed selection. Load-bearing execution: `NOT_EXECUTED`. Submission claim: **NOT** marked as `true`.

See `README.md` for details.

## Troubleshooting

### ModuleNotFoundError: ale_py
```bash
pip install ale-py gymnasium
```

### Cannot connect to OpenJEV
```bash
# Check if server is running
curl http://127.0.0.1:3000/v1/systemone

# If "Connection refused":
# 1. Verify OpenJEV is installed: pip list | grep openjev
# 2. Start it: python -m openjev.server --port 3000
# 3. Check logs for errors
```

### Git push fails during game
Ensure:
1. You're on `competition/final-integration-v01`
2. Worktree is clean before running (no uncommitted changes)
3. Origin has push permission (not a fork with restricted access)
4. Not behind main (rebase if needed)

### "results.json is immutable" error
The competition uses append-only results recording. If you need to reset:

```bash
git checkout results.json
```

## Results Recording

After each game, the harness:
1. Appends a new record to `results.json` with full metadata
2. Writes per-step trace (gzipped JSONL) to `runs/run_NNNN_seedN.jsonl.gz`
3. Commits both with message: `results: run N, score M`
4. Pushes to origin

Each record includes:
- **Seed, score, steps, frames, lives lost**
- **Latency percentiles (p50, p95)**
- **Model attribution**: `served_model`, `provider`, `requested_model`
- **Trace file**: pointer to compressed per-step log
- **MMR proof**: Merkle proof of game execution chain

Run `python scripts/validate_results.py` to verify structural integrity.

## Verification

### Quick Check
```bash
python -m pytest -q
```

### Competition Lineage
```bash
python scripts/verify_competition_lineage.py
```

Verifies the qualified `UFA-JEV-COMP-BP-*` governance chain is intact.

### Breakpoint Verification (Legacy)
```bash
python scripts/verify_breakpoints.py
```

Historical chain; currently FAILs on mutable results.json (known issue).

## What Gets Committed

After each game:
- `results.json` (appended, never rewritten)
- `runs/run_NNNN_seedN_decider.jsonl.gz` (per-step trace)
- Commit message: `results: run N, score M`

**What is NOT committed**:
- `.env` (API keys)
- `.venv/` (ignored)
- Raw ROM (cached locally, not in repo)
- Model cache (e.g., `~/.cache/huggingface/`, `~/.ollama/`)

## Performance and Costs

### Local (Zero Cloud Cost)
- **Scripted**: <1 ms/decision, instant
- **Ollama local**: 200–500 ms/decision, depends on model and hardware
- **OpenJEV local**: 100–300 ms/decision, MLX-optimized on Apple Silicon

### Remote (API Costs)
- **TypeSafe JEV**: Provider determines; likely $0.001–0.01 per decision
- **Claude (Haiku)**: ~$0.0001/input token, $0.0004/output token (current pricing)
- **GPT-4 Mini**: ~$0.15/1M input, $0.6/1M output tokens

**Estimate for 5 games (avg 200 steps)**: ~$0.10–1.00 per provider per suite depending on model and token cost.

## Next Steps

1. **Run the scripted baseline** (fastest smoke test)
2. **Set up Ollama** locally and run the Ollama baseline
3. **Set up OpenJEV** (if you have access) and run the OpenJEV lane
4. **Test a remote provider** (if you have API keys)
5. **Verify results** with `python scripts/validate_results.py`
6. **Push results** (automatic during runs, or manual `git push`)

## For Competition Submission

Ensure:
1. At least 5 fixed-seed JEV-compatible games
2. At least 5 comparable LLM baseline games
3. All appended to `results.json` in the repo
4. All committed and pushed to the default branch
5. `verify_competition_lineage.py` PASSES
6. README accurately describes what ran and what is blocked

---

**Questions?** Check the main `README.md` or the governance docs in `governance/lineage/`.

**Last Updated**: 2026-09-28 (Codex + Claude Haiku 4.5)
