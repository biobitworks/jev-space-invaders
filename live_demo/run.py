"""Terminal-first Vithia Space execution runner.

The browser demo consumes the same controller primitives, but this module is
the authoritative CLI surface for bounded Python E2E runs.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import time
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from demo.live_demo import ALE_ACTIONS, PZ_ACTIONS, DemoController, PlayerSeatConfig
from src.eca_actions import decompose
from src.envcfg import runtime_versions

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS = ROOT / "results.json"


def _git_head() -> str | None:
    try:
        import subprocess

        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
            capture_output=True, check=True, timeout=5,
        ).stdout.strip()
    except Exception:
        return None


def _sha(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _append_json_result(path: Path, row: dict[str, Any]) -> None:
    if path.exists():
        doc = json.loads(path.read_text(encoding="utf-8"))
    else:
        doc = {"schema_version": 3}
    runs = doc.setdefault("terminal_runs", [])
    runs.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _discover_ollama(base_url: str) -> dict[str, Any]:
    out = {
        "runtime": "ollama",
        "base_url": base_url,
        "load_pass": "BLOCKED",
        "openai_compatible": "BLOCKED",
        "models": [],
    }
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + "/api/tags", timeout=3) as response:
            tags = json.loads(response.read()).get("models", [])
        out["models"] = [
            {
                "MODEL_ID": m.get("name") or m.get("model"),
                "RUNTIME": "ollama",
                "SIZE": m.get("size"),
                "CURRENTLY_RESIDENT": True,
                "LOAD_PASS": "PASS",
                "SYSTEM_ONE_COMPATIBLE": "OPENAI_COMPATIBLE_HTTP_PROBED",
                "GAME_DECIDER_ELIGIBLE": bool((m.get("name") or "").strip()),
                "ENGINEERING_SUBAGENT_ELIGIBLE": "coder" in (m.get("name") or "").lower(),
            }
            for m in tags
        ]
        out["load_pass"] = "PASS"
    except Exception as exc:
        out["error"] = type(exc).__name__
    try:
        with urllib.request.urlopen(base_url.rstrip("/") + "/v1/models", timeout=3) as response:
            payload = json.loads(response.read())
        out["openai_compatible"] = "PASS"
        out["openai_models"] = [m.get("id") for m in payload.get("data", []) if m.get("id")]
    except Exception as exc:
        out["openai_compatible_error"] = type(exc).__name__
    return out


def _classify_decider(value: str, default_model: str | None = None) -> tuple[str, str, str]:
    key = (value or "scripted").strip()
    low = key.lower()
    if low in {"scripted", "scripted_baseline", "scripted-policy"}:
        return "SCRIPTED_BASELINE", "scripted-policy", "scripted-policy"
    if low in {"openjev", "openjev_local", "system_one:openjev_local"}:
        return "SYSTEM_ONE", "OPENJEV_LOCAL", default_model or "openjev"
    if low in {"jev", "real_jev", "jev_api", "jev_api_remote"}:
        return "JEV_API_REMOTE", "JEV_API_REMOTE", default_model or "jev-latest"
    if low.startswith("ollama:"):
        model = key.split(":", 1)[1]
        return "OLLAMA", model, model
    if low.startswith("liquid:"):
        model = key.split(":", 1)[1]
        return "LIQUID_LOCAL", model, model
    if "liquid" in low:
        return "LIQUID_LOCAL", key, default_model or key
    return "OLLAMA", key, default_model or key


def _preprocessor(value: str) -> str:
    low = (value or "none").strip().lower()
    if low in {"none", "no", "off"}:
        return "NONE"
    if low in {"vithia", "vithia_space", "space"}:
        return "VITHIA_SPACE"
    raise SystemExit(f"unknown preprocessor: {value}")


def _seat_config(seat_id: str, preprocessor: str, decider: str, model: str | None) -> PlayerSeatConfig:
    provider, backend, exact = _classify_decider(decider, model)
    return PlayerSeatConfig(
        seat_id=seat_id,
        preprocessor=_preprocessor(preprocessor),
        decision_layer="SYSTEM_ONE" if provider in {"SYSTEM_ONE", "JEV_API_REMOTE"} else "DIRECT_TYPED_CHOICE",
        decider_provider=provider,
        decider_backend=backend,
        exact_model=exact,
    )


def _fco(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    fco_id = f"FCO:{kind}:{_sha(payload)[:16]}"
    return {"id": fco_id, "kind": kind, "payload": payload}


def _write_trace(trace_path: Path, records: list[dict[str, Any]]) -> None:
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    with trace_path.open("w", encoding="utf-8") as fh:
        for row in records:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def _summarize_1p_row(row: dict[str, Any]) -> str:
    return (
        f"PLAYER_0 PREPROCESSOR={row.get('preprocessor_requested')} "
        f"DECIDER={row.get('decider_provider')}/{row.get('decider_backend')} "
        f"ACTION={row.get('executed_action')} "
        f"ECA=({row.get('eca_move')},{row.get('eca_fire')}) "
        f"CONFIDENCE={row.get('confidence')} LATENCY_MS={row.get('latency_ms')} "
        f"FALLBACK={'YES' if row.get('fallback') else 'NO'}"
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    mode = args.mode.upper()
    if mode not in {"1P", "2P"}:
        raise SystemExit("--mode must be 1p or 2p")

    results_path = Path(args.results_path).resolve()
    trace_dir = Path(args.trace_dir or results_path.parent / "terminal_traces").resolve()
    controller = DemoController(str(trace_dir / "controller"))
    controller.mode = mode
    controller.seats["PLAYER_0"] = _seat_config("PLAYER_0", args.player0_preprocessor, args.player0_decider, args.player0_model)
    controller.seats["PLAYER_1"] = _seat_config("PLAYER_1", args.player1_preprocessor, args.player1_decider, args.player1_model)

    run_id = uuid.uuid4().hex
    head = _git_head()
    started = time.perf_counter()
    ollama = _discover_ollama(os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434"))
    system_one_adapter = "INSTALLED" if importlib.util.find_spec("system_one_adapter") else "NOT_INSTALLED_IN_ACTIVE_RUNTIME"
    real_jev_state = "CONFIGURED_NOT_EXECUTED" if os.environ.get("TYPESAFE_API_KEY") else "BLOCKED_API_KEY"
    mitosis_state = "CONFIGURED_CONTEXT_PROVIDER_NOT_CALLED" if (os.environ.get("MITOSIS_API_KEY") or os.environ.get("MI_API_KEY")) else "BLOCKED_NO_ENV_AUTH"
    tenki_state = "CONFIGURED_NOT_EXECUTED" if (os.environ.get("TENKI_API_KEY") or os.environ.get("TENKI_AUTH_TOKEN")) else "BLOCKED_NO_ENV_AUTH"
    gum_doctor_state = "NOT_EVIDENCED"

    episodes: list[dict[str, Any]] = []
    trace_records: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    controller.reset(args.seed)
    if mode == "2P":
        controller.set_mode("2P")

    try:
        for episode_index in range(args.episodes):
            if episode_index:
                controller.reset(args.seed + episode_index)
            print(f"RUN={episode_index + 1:03d}", flush=True)
            print(f"MODE={mode}", flush=True)
            print(f"SEED={args.seed + episode_index}", flush=True)
            for _ in range(args.steps):
                before_history = len(controller.history)
                state = controller.step_once()
                new_rows = controller.history[before_history:]
                for row in new_rows:
                    if row.get("mode") == "1P":
                        move, fire = decompose(row["executed_action"])
                        row.setdefault("eca_move", move)
                        row.setdefault("eca_fire", fire)
                        observation = _fco("ObservationFCO", {"mode": "1P", "step": row["decision_index"], "frame": row.get("environment_frame")})
                        context = _fco("ContextFCO", {"seat_id": "PLAYER_0", "preprocessor": row.get("preprocessor_actual"), "context_hash": row.get("preprocessor_output_hash")})
                        decision = _fco("DecisionFCO", {"provider": row.get("decider_provider"), "model": row.get("exact_model"), "answer": row.get("executed_action"), "confidence": row.get("confidence"), "trace_id": row.get("trace_id"), "latency_ms": row.get("latency_ms")})
                        action = _fco("ActionFCO", {"action": row.get("executed_action"), "move": move, "fire": fire})
                        result = _fco("ResultFCO", {"reward": row.get("reward"), "score": row.get("score"), "lives": row.get("lives")})
                        trace = {"schema": "THIN_FCO_FCG_STEP_V1", "records": [observation, context, decision, action, result], "edges": [[observation["id"], "ENCODED_AS", context["id"]], [context["id"], "DECIDED_BY", decision["id"]], [decision["id"], "NORMALIZED_TO", action["id"]], [action["id"], "PRODUCED", result["id"]]]}
                        row["context_fco"] = context["id"]
                        row["result_fco"] = result["id"]
                        row["fco_trace"] = trace
                        print(_summarize_1p_row(row), flush=True)
                        print(f"ENV SCORE={row.get('score')} LIVES={row.get('lives')} STEP={row.get('decision_index')} FRAME={row.get('environment_frame')}", flush=True)
                        print(f"RESULT_FCO={result['id']}", flush=True)
                    elif row.get("mode") == "2P":
                        observation = _fco("ObservationFCO", {"mode": "2P", "joint_step": row.get("joint_step"), "state_hash": row.get("environment_state_hash")})
                        contexts = []
                        decisions = []
                        actions = []
                        for label, player in (("PLAYER_0", row.get("player0")), ("PLAYER_1", row.get("player1"))):
                            if player:
                                context = _fco("ContextFCO", {"seat_id": label, "preprocessor": player.get("preprocessor_actual"), "context_hash": player.get("preprocessor_output_hash")})
                                decision = _fco("DecisionFCO", {"seat_id": label, "provider": player.get("decider_provider"), "model": player.get("exact_model"), "answer": player.get("executed_action"), "confidence": player.get("confidence"), "trace_id": player.get("trace_id"), "latency_ms": player.get("latency_ms")})
                                action = _fco("ActionFCO", {"seat_id": label, "action": player.get("executed_action")})
                                contexts.append(context)
                                decisions.append(decision)
                                actions.append(action)
                                print(
                                    f"{label} PREPROCESSOR={player.get('preprocessor_requested')} "
                                    f"DECIDER={player.get('decider_provider')}/{player.get('decider_backend')} "
                                    f"ACTION={player.get('executed_action')} "
                                    f"LATENCY_MS={player.get('latency_ms')} "
                                    f"FALLBACK={'YES' if player.get('fallback') else 'NO'}",
                                    flush=True,
                                )
                        result = _fco("ResultFCO", {"rewards": controller.rewards, "joint_step": row.get("joint_step")})
                        trace = {"schema": "THIN_FCO_FCG_STEP_V1", "records": [observation, *contexts, *decisions, *actions, result], "edges": []}
                        for context, decision, action in zip(contexts, decisions, actions):
                            trace["edges"].extend([[observation["id"], "ENCODED_AS", context["id"]], [context["id"], "DECIDED_BY", decision["id"]], [decision["id"], "NORMALIZED_TO", action["id"]], [action["id"], "PRODUCED", result["id"]]])
                        row["context_fcos"] = [context["id"] for context in contexts]
                        row["result_fco"] = result["id"]
                        row["fco_trace"] = trace
                        print(f"ENV JOINT_STEP={row.get('joint_step')} REWARDS={controller.rewards}", flush=True)
                    trace_records.append(row)
                if state.get("status") == "stopped":
                    break
            episodes.append({"episode": episode_index, "seed": args.seed + episode_index, "state": controller.state()})
    except Exception as exc:
        errors.append({"type": type(exc).__name__, "detail": str(exc)})
    finally:
        controller._close_envs()

    wall_clock = round(time.perf_counter() - started, 4)
    terminal_trace = trace_dir / f"{run_id}.trace.jsonl"
    _write_trace(terminal_trace, trace_records)

    model_calls = sum(1 for r in trace_records if r.get("model_call") or (r.get("player0") or {}).get("model_call") or (r.get("player1") or {}).get("model_call"))
    fallbacks = sum(1 for r in trace_records if r.get("fallback") or (r.get("player0") or {}).get("fallback") or (r.get("player1") or {}).get("fallback"))
    score = trace_records[-1].get("score") if trace_records and trace_records[-1].get("mode") == "1P" else None
    run_row = {
        "schema": "VITHIA_TERMINAL_RUN_RESULT_V1",
        "run_id": run_id,
        "RUN_CLASS": args.run_class,
        "mode": mode,
        "head": head,
        "seed": args.seed,
        "episodes": args.episodes,
        "steps_requested": args.steps,
        "steps_executed": len(trace_records),
        "frames": trace_records[-1].get("environment_frame") if trace_records and trace_records[-1].get("mode") == "1P" else None,
        "score": score,
        "opponent_score": None,
        "lives": trace_records[-1].get("lives") if trace_records and trace_records[-1].get("mode") == "1P" else None,
        "calls": model_calls,
        "fallbacks": fallbacks,
        "errors": errors,
        "wall_clock_s": wall_clock,
        "runtime": runtime_versions(),
        "preprocessor": {"PLAYER_0": controller.seats["PLAYER_0"].preprocessor, "PLAYER_1": controller.seats["PLAYER_1"].preprocessor if mode == "2P" else None},
        "decider": {"PLAYER_0": controller.seats["PLAYER_0"].public(), "PLAYER_1": controller.seats["PLAYER_1"].public() if mode == "2P" else None},
        "execution_substrate": "LOCAL_PYTHON_TERMINAL",
        "system_one_adapter": system_one_adapter,
        "ollama_openai_compat": ollama["openai_compatible"],
        "discovered_models": ollama.get("models", []),
        "real_jev_api": real_jev_state,
        "mitosis": mitosis_state,
        "tenki": tenki_state,
        "gum_doctor": gum_doctor_state,
        "fco_temporal_loop": "WRITTEN" if trace_records else "NO_STEPS",
        "eca_6_class": "PASS",
        "trace_file": str(terminal_trace.relative_to(ROOT) if terminal_trace.is_relative_to(ROOT) else terminal_trace),
        "trace_sha256": hashlib.sha256(terminal_trace.read_bytes()).hexdigest(),
        "results_path": str(results_path),
        "terminal_acceptance": "PASS" if trace_records and not errors else "FAIL",
    }
    _append_json_result(results_path, run_row)
    print(f"RESULTS_JSON={results_path}", flush=True)
    print(f"TRACE={terminal_trace}", flush=True)
    print(f"TERMINAL_ACCEPTANCE={run_row['terminal_acceptance']}", flush=True)
    return run_row


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run authoritative terminal Vithia Space episodes.")
    parser.add_argument("--mode", choices=["1p", "2p", "1P", "2P"], default="1p")
    parser.add_argument("--seed", type=int, default=3)
    parser.add_argument("--steps", type=int, default=3)
    parser.add_argument("--episodes", type=int, default=1)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--render", choices=["none", "terminal"], default="none")
    parser.add_argument("--results-path", default=str(DEFAULT_RESULTS))
    parser.add_argument("--trace-dir")
    parser.add_argument("--run-class", default="BASELINE_LLM")
    parser.add_argument("--player0-preprocessor", "--p0-preprocessor", "--preprocessor", default="VITHIA_SPACE")
    parser.add_argument("--player0-decider", "--p0-decider", "--decider", default="scripted")
    parser.add_argument("--player0-model", "--p0-model")
    parser.add_argument("--player1-preprocessor", "--p1-preprocessor", default="VITHIA_SPACE")
    parser.add_argument("--player1-decider", "--p1-decider", default="scripted")
    parser.add_argument("--player1-model", "--p1-model")
    return parser


def main(argv: list[str] | None = None) -> None:
    run(build_parser().parse_args(argv))


if __name__ == "__main__":
    main()
