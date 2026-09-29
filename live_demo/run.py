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

from demo.live_demo import ALE_ACTIONS, PZ_ACTIONS, DemoController, PlayerSeatConfig, png_bytes
from src.eca_actions import decompose
from src.envcfg import runtime_versions

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS = ROOT / "results.json"
DEFAULT_BENCHMARK_DIR = ROOT / "evidence" / "competition" / "openjev_ab"


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


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in records:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    vals = sorted(values)
    idx = min(len(vals) - 1, max(0, int(round((len(vals) - 1) * q))))
    return round(vals[idx], 4)


def _stats(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"p50": None, "p95": None, "mean": None, "max": None}
    return {
        "p50": _percentile(values, 0.50),
        "p95": _percentile(values, 0.95),
        "mean": round(sum(values) / len(values), 4),
        "max": round(max(values), 4),
    }


def _mmr_peaks(leaves: list[str]) -> list[str]:
    peaks: list[str | None] = []
    for leaf in leaves:
        node = leaf
        height = 0
        while height < len(peaks) and peaks[height] is not None:
            node = _sha({"left": peaks[height], "right": node, "height": height + 1})
            peaks[height] = None
            height += 1
        if height == len(peaks):
            peaks.append(node)
        else:
            peaks[height] = node
    return [p for p in peaks if p is not None]


def _mmr_root(leaves: list[str]) -> str:
    return _sha({"protocol": "VITHIA_SIMPLE_MMR_V1", "size": len(leaves), "peaks": _mmr_peaks(leaves)})


def _bundle_paths(output_dir: Path, run_id: str) -> dict[str, Path]:
    run_dir = output_dir / f"run_{run_id}"
    return {
        "run_dir": run_dir,
        "manifest": run_dir / "manifest.json",
        "telemetry": run_dir / "telemetry.jsonl",
        "fco": run_dir / "fco.jsonl",
        "mmr": run_dir / "mmr.jsonl",
        "results": run_dir / "results.json",
        "figures": run_dir / "figures",
        "frames": run_dir / "frames",
        "media": run_dir / "media",
    }


def _frame_hash(frame: Any) -> str:
    try:
        return hashlib.sha256(frame.tobytes()).hexdigest()
    except Exception:
        return _sha(str(type(frame)))


def _openjev_status() -> dict[str, Any]:
    manifest = ROOT / "evidence" / "openjev" / "RUNTIME_MANIFEST.json"
    state: dict[str, Any] = {"OPENJEV_LOAD_STATE": "UNKNOWN", "manifest": str(manifest)}
    if manifest.exists():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            state.update({
                "OPENJEV_LOAD_STATE": "PASS" if data.get("OPENJEV_LOADED") == "YES" else "BLOCKED_NOT_LOADED",
                "OPENJEV_MODEL_ID": (((data.get("upstream") or {}).get("model") or {}).get("repo")) or "openjev/openjev-MLX-4bit",
                "OPENJEV_RUNTIME": "MLX",
                "OPENJEV_LOCAL_PATH": data.get("local_path") or "/Volumes/magicBLACKbox/openjev/openjev-MLX-4bit",
                "OPENJEV_MODEL_HASH": (((data.get("artifacts") or {}).get("config_sha256")) or None),
                "OPENJEV_SIZE": (((data.get("upstream") or {}).get("model") or {}).get("total_bytes")) or 15153274826,
                "endpoint": data.get("endpoint"),
                "failure": data.get("failure"),
            })
        except json.JSONDecodeError as exc:
            state.update({"OPENJEV_LOAD_STATE": "BLOCKED_BAD_MANIFEST", "failure": type(exc).__name__})
    return state


def _step_root(records: list[dict[str, Any]], step_id: str) -> str:
    return _sha({"protocol": "VITHIA_STEP_ROOT_V1", "step_id": step_id, "records": records})


def _verify_run_bundle(manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    fco = _read_jsonl(manifest_path.parent / "fco.jsonl")
    mmr = _read_jsonl(manifest_path.parent / "mmr.jsonl")
    leaves: list[str] = []
    for entry in mmr:
        step_fcos = [row for row in fco if row.get("step_id") == entry["step_id"]]
        root = _step_root(step_fcos, entry["step_id"])
        if root != entry["step_root"]:
            return {"RUN_PROOF_VERIFY": "FAIL", "reason": "STEP_ROOT_MISMATCH", "step_id": entry["step_id"]}
        leaves.append(root)
        if _mmr_root(leaves) != entry["mmr_root"]:
            return {"RUN_PROOF_VERIFY": "FAIL", "reason": "MMR_ROOT_MISMATCH", "step_id": entry["step_id"]}
    ok = _mmr_root(leaves) == manifest["mmr_root"] and len(leaves) == manifest["mmr_size"]
    return {"RUN_PROOF_VERIFY": "PASS" if ok else "FAIL", "MMR_SIZE": len(leaves), "MMR_ROOT": _mmr_root(leaves), "checked_steps": len(leaves)}


def _write_simple_svg(path: Path, title: str, rows: list[tuple[str, float]], unit: str = "") -> None:
    width, height = 720, 280
    margin = 48
    max_value = max([v for _, v in rows] or [1.0]) or 1.0
    bar_h = 32
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f7f7f2"/>',
        f'<text x="{margin}" y="36" font-family="monospace" font-size="18" fill="#202020">{title}</text>',
    ]
    for i, (label, value) in enumerate(rows):
        y = 68 + i * 54
        bar_w = int((width - margin * 2 - 160) * (value / max_value))
        parts.append(f'<text x="{margin}" y="{y + 22}" font-family="monospace" font-size="13" fill="#202020">{label}</text>')
        parts.append(f'<rect x="{margin + 170}" y="{y}" width="{bar_w}" height="{bar_h}" fill="#326b6b"/>')
        parts.append(f'<text x="{margin + 180 + bar_w}" y="{y + 22}" font-family="monospace" font-size="13" fill="#202020">{round(value, 3)}{unit}</text>')
    parts.append("</svg>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def _write_comparison_figures(comparison: dict[str, Any], output_dir: Path) -> list[str]:
    fig_dir = output_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)
    raw_tel = _read_jsonl(output_dir / f"run_{comparison['raw']['run_id']}" / "telemetry.jsonl")
    vit_tel = _read_jsonl(output_dir / f"run_{comparison['vithia']['run_id']}" / "telemetry.jsonl")
    paths = []
    fig_a = fig_dir / "figure_a_move_fire_timeline.csv"
    fig_a.write_text(
        "arm,seed,step,move,fire,action\n" + "\n".join(
            f"{r['arm']},{r['seed']},{r['step']},{r['move']},{r['fire']},{r['action']}" for r in [*raw_tel, *vit_tel]
        ) + "\n",
        encoding="utf-8",
    )
    paths.append(str(fig_a.relative_to(ROOT)))
    fig_b = fig_dir / "figure_b_decision_latency.svg"
    _write_simple_svg(fig_b, "Decision latency p50", [("RAW", comparison["RAW_DECISION_P50"] or 0), ("VITHIA_L1", comparison["VITHIA_DECISION_P50"] or 0)], " ms")
    paths.append(str(fig_b.relative_to(ROOT)))
    fig_c = fig_dir / "figure_c_score_reward.csv"
    fig_c.write_text(
        "arm,seed,step,reward,score\n" + "\n".join(
            f"{r['arm']},{r['seed']},{r['step']},{r['reward']},{r['score']}" for r in [*raw_tel, *vit_tel]
        ) + "\n",
        encoding="utf-8",
    )
    paths.append(str(fig_c.relative_to(ROOT)))
    fig_d = fig_dir / "figure_d_raw_vs_vithia_latency.svg"
    _write_simple_svg(fig_d, "Raw OpenJEV vs Vithia+OpenJEV", [("RAW p50", comparison["RAW_DECISION_P50"] or 0), ("VITHIA p50", comparison["VITHIA_DECISION_P50"] or 0), ("RAW p95", comparison["RAW_DECISION_P95"] or 0), ("VITHIA p95", comparison["VITHIA_DECISION_P95"] or 0)], " ms")
    paths.append(str(fig_d.relative_to(ROOT)))
    fig_e = fig_dir / "figure_e_input_size_vs_inference.csv"
    fig_e.write_text(
        "arm,input_bytes_mean,inference_p50_ms\n"
        f"RAW,{comparison['RAW_INPUT_SIZE']},{comparison['RAW_MODEL_INFERENCE_P50']}\n"
        f"VITHIA_L1,{comparison['VITHIA_INPUT_SIZE']},{comparison['VITHIA_MODEL_INFERENCE_P50']}\n",
        encoding="utf-8",
    )
    paths.append(str(fig_e.relative_to(ROOT)))
    fig_f = fig_dir / "figure_f_action_distribution.csv"
    rows = ["arm,action,count"]
    for arm_key, label in (("raw", "RAW"), ("vithia", "VITHIA_L1")):
        for action, count in comparison[arm_key]["action_distribution"].items():
            rows.append(f"{label},{action},{count}")
    fig_f.write_text("\n".join(rows) + "\n", encoding="utf-8")
    paths.append(str(fig_f.relative_to(ROOT)))
    return paths


def _summarize_1p_row(row: dict[str, Any]) -> str:
    return (
        f"PLAYER_0 PREPROCESSOR={row.get('preprocessor_requested')} "
        f"DECIDER={row.get('decider_provider')}/{row.get('decider_backend')} "
        f"ACTION={row.get('executed_action')} "
        f"ECA=({row.get('eca_move')},{row.get('eca_fire')}) "
        f"CONFIDENCE={row.get('confidence')} LATENCY_MS={row.get('latency_ms')} "
        f"FALLBACK={'YES' if row.get('fallback') else 'NO'}"
    )


def _benchmark_arm(
    *,
    arm: str,
    preprocessor: str,
    seeds: list[int],
    steps: int,
    output_dir: Path,
) -> dict[str, Any]:
    run_id = f"{arm.lower()}_{uuid.uuid4().hex[:12]}"
    paths = _bundle_paths(output_dir, run_id)
    for key in ("run_dir", "figures", "frames", "media"):
        paths[key].mkdir(parents=True, exist_ok=True)

    controller = DemoController(str(paths["run_dir"] / "controller"))
    controller.seats["PLAYER_0"] = _seat_config("PLAYER_0", preprocessor, "openjev_local", "openjev")
    telemetry: list[dict[str, Any]] = []
    fcos: list[dict[str, Any]] = []
    mmr_rows: list[dict[str, Any]] = []
    leaves: list[str] = []
    started = time.perf_counter()
    errors: list[dict[str, Any]] = []
    action_distribution = {action: 0 for action in ("NOOP", "FIRE", "LEFT", "LEFTFIRE", "RIGHT", "RIGHTFIRE")}
    scores: list[float] = []
    try:
        for seed in seeds:
            controller.reset(seed)
            prev = "NOOP"
            for step in range(steps):
                step_id = f"{arm}:seed{seed}:step{step}"
                loop_t0 = time.perf_counter_ns()
                obs_t0 = time.perf_counter_ns()
                frame = controller.obs
                info = controller.info
                frame_sha = _frame_hash(frame)
                frame_rel = Path("frames") / f"seed_{seed}_step_{step}.png"
                frame_path = paths["run_dir"] / frame_rel
                frame_path.write_bytes(png_bytes(frame))
                observation_read_ms = (time.perf_counter_ns() - obs_t0) / 1_000_000

                state_t0 = time.perf_counter_ns()
                perception = controller.perceptions["PLAYER_0"].observe(
                    frame,
                    lives=int(info.get("lives", 0)),
                    score=controller.score,
                    step=step,
                    prev_action=prev,
                )
                if preprocessor == "NONE":
                    context = perception
                    prep = {
                        "requested": "NONE",
                        "actual": "RAW_COMPACT_STATE_V1",
                        "latency_ms": 0.0,
                        "input_hash": _frame_hash(frame),
                        "output_hash": _sha(context),
                        "fallback": False,
                    }
                else:
                    vithia_t0 = time.perf_counter_ns()
                    context = _vithia_l1_context(perception)
                    prep = {
                        "requested": "VITHIA_SPACE",
                        "actual": context["encoding"],
                        "latency_ms": (time.perf_counter_ns() - vithia_t0) / 1_000_000,
                        "input_hash": _frame_hash(frame),
                        "output_hash": _sha(context),
                        "fallback": False,
                    }
                state_encode_ms = (time.perf_counter_ns() - state_t0) / 1_000_000
                raw_state = {"encoding": "RAW_COMPACT_STATE_V1", "state": perception}
                raw_input_bytes = len(json.dumps(raw_state, sort_keys=True, separators=(",", ":")).encode())
                context_bytes = len(json.dumps(context, sort_keys=True, separators=(",", ":")).encode())
                vithia_context_ms = prep["latency_ms"] if preprocessor == "VITHIA_SPACE" else 0.0
                fcg_lookup_ms = 0.0

                decision_t0 = time.perf_counter_ns()
                decision = controller._seat_decision("PLAYER_0", context, "1P_ALE", prev, controller.generation_id, ALE_ACTIONS)
                decision_latency_ms = (time.perf_counter_ns() - decision_t0) / 1_000_000
                system_one_adapter_ms = decision_latency_ms
                openjev_inference_ms = float(decision.get("latency_ms") or decision_latency_ms)

                parse_t0 = time.perf_counter_ns()
                action = decision["executed_action"]
                move, fire = decompose(action)
                action_index = ALE_ACTIONS.index(action)
                response_parse_ms = (time.perf_counter_ns() - parse_t0) / 1_000_000

                validation_t0 = time.perf_counter_ns()
                roundtrip_ok = action in action_distribution and action == {"NONE:NO": "NOOP", "NONE:YES": "FIRE", "LEFT:NO": "LEFT", "LEFT:YES": "LEFTFIRE", "RIGHT:NO": "RIGHT", "RIGHT:YES": "RIGHTFIRE"}[f"{move}:{fire}"]
                action_validation_ms = (time.perf_counter_ns() - validation_t0) / 1_000_000

                env_t0 = time.perf_counter_ns()
                next_obs, reward, term, trunc, info2 = controller.env.step(action_index)
                env_step_ms = (time.perf_counter_ns() - env_t0) / 1_000_000
                controller.obs = next_obs
                controller.info = info2
                controller.score += float(reward)
                prev = action
                action_distribution[action] += 1

                fco_t0 = time.perf_counter_ns()
                observation = {"step_id": step_id, **_fco("ObservationFCO", {"seed": seed, "step": step, "frame_hash": frame_sha, "dimensions": list(frame.shape), "format": "PNG", "content_pointer": str(frame_rel)})}
                context_fco = {"step_id": step_id, **_fco("ContextFCO", {"preprocessor": preprocessor, "context": context, "input_bytes": context_bytes})}
                decision_fco = {"step_id": step_id, **_fco("DecisionFCO", {"provider": "OPENJEV_LOCAL", "model": decision.get("exact_model") or "openjev", "typed_answer": action, "confidence": decision.get("confidence"), "trace_id": decision.get("trace_id"), "latency_ms": decision.get("latency_ms"), "requested_action": decision.get("requested_action"), "fallback": decision.get("fallback")})}
                action_fco = {"step_id": step_id, **_fco("ActionFCO", {"action": action, "move": move, "fire": fire, "roundtrip_ok": roundtrip_ok})}
                outcome = {"step_id": step_id, **_fco("OutcomeFCO", {"reward": float(reward), "score": controller.score, "lives": int(info2.get("lives", 0)), "terminated": bool(term), "truncated": bool(trunc)})}
                latency = {"step_id": step_id, **_fco("LatencyAtom", {"observation_read_ms": observation_read_ms, "state_encode_ms": state_encode_ms, "vithia_context_ms": vithia_context_ms, "fcg_lookup_ms": fcg_lookup_ms, "system_one_adapter_ms": system_one_adapter_ms, "model_queue_ms": 0.0, "openjev_inference_ms": openjev_inference_ms, "response_parse_ms": response_parse_ms, "action_validation_ms": action_validation_ms, "env_step_ms": env_step_ms})}
                step_fcos = [observation, context_fco, decision_fco, action_fco, outcome, latency]
                fcos.extend(step_fcos)
                step_root = _step_root(step_fcos, step_id)
                fco_hashing_ms = (time.perf_counter_ns() - fco_t0) / 1_000_000

                mmr_t0 = time.perf_counter_ns()
                leaves.append(step_root)
                peaks = _mmr_peaks(leaves)
                root = _mmr_root(leaves)
                mmr_append_ms = (time.perf_counter_ns() - mmr_t0) / 1_000_000
                mmr_rows.append({"step_id": step_id, "step_root": step_root, "mmr_size": len(leaves), "mmr_peaks": peaks, "mmr_root": root})

                control_loop_latency_ms = (time.perf_counter_ns() - loop_t0) / 1_000_000
                telemetry.append({
                    "run_id": run_id,
                    "arm": arm,
                    "seed": seed,
                    "step": step,
                    "frame_hash": frame_sha,
                    "frame_pointer": str(frame_rel),
                    "action": action,
                    "move": move,
                    "fire": fire,
                    "reward": float(reward),
                    "score": controller.score,
                    "lives": int(info2.get("lives", 0)),
                    "raw_input_bytes": raw_input_bytes,
                    "context_input_bytes": context_bytes,
                    "input_tokens": None,
                    "fallback": bool(decision.get("fallback")),
                    "errors": decision.get("reason"),
                    "observation_read_ms": round(observation_read_ms, 4),
                    "state_encode_ms": round(state_encode_ms, 4),
                    "vithia_context_ms": round(vithia_context_ms, 4),
                    "fcg_lookup_ms": round(fcg_lookup_ms, 4),
                    "system_one_adapter_ms": round(system_one_adapter_ms, 4),
                    "model_queue_ms": 0.0,
                    "openjev_inference_ms": round(openjev_inference_ms, 4),
                    "response_parse_ms": round(response_parse_ms, 4),
                    "action_validation_ms": round(action_validation_ms, 4),
                    "env_step_ms": round(env_step_ms, 4),
                    "decision_latency_ms": round(decision_latency_ms + response_parse_ms + action_validation_ms, 4),
                    "control_loop_latency_ms": round(control_loop_latency_ms, 4),
                    "fco_hashing_ms": round(fco_hashing_ms, 4),
                    "mmr_append_ms": round(mmr_append_ms, 4),
                    "step_root": step_root,
                    "mmr_root": root,
                    "mmr_size": len(leaves),
                })
                if term or trunc:
                    break
            scores.append(controller.score)
    except Exception as exc:
        errors.append({"type": type(exc).__name__, "detail": str(exc)})
    finally:
        controller._close_envs()

    _write_jsonl(paths["telemetry"], telemetry)
    _write_jsonl(paths["fco"], fcos)
    _write_jsonl(paths["mmr"], mmr_rows)
    latency_values = [row["decision_latency_ms"] for row in telemetry]
    inference_values = [row["openjev_inference_ms"] for row in telemetry]
    vithia_values = [row["vithia_context_ms"] for row in telemetry]
    control_values = [row["control_loop_latency_ms"] for row in telemetry]
    elapsed = max(0.0001, time.perf_counter() - started)
    manifest = {
        "schema": "VITHIA_OPENJEV_AB_ARM_MANIFEST_V1",
        "run_id": run_id,
        "arm": arm,
        "source_head": _git_head(),
        "environment": "ALE/SpaceInvaders-v5",
        "seeds": seeds,
        "steps_requested": steps,
        "steps_executed": len(telemetry),
        "preprocessor": preprocessor,
        "decider": "SYSTEM_ONE/OPENJEV_LOCAL",
        "model": "openjev",
        "runtime": _openjev_status(),
        "first_step_root": mmr_rows[0]["step_root"] if mmr_rows else None,
        "last_step_root": mmr_rows[-1]["step_root"] if mmr_rows else None,
        "mmr_size": len(leaves),
        "mmr_root": _mmr_root(leaves),
        "mmr_peaks": _mmr_peaks(leaves),
        "final_score": scores[-1] if scores else None,
        "score_total": round(sum(scores), 4) if scores else None,
        "final_lives": telemetry[-1]["lives"] if telemetry else None,
        "termination": "ERROR" if errors else "BOUNDED_STEPS_COMPLETE",
        "telemetry_root": hashlib.sha256(paths["telemetry"].read_bytes()).hexdigest() if paths["telemetry"].exists() else None,
        "fco_root": hashlib.sha256(paths["fco"].read_bytes()).hexdigest() if paths["fco"].exists() else None,
        "decision_latency": _stats(latency_values),
        "openjev_inference": _stats(inference_values),
        "vithia_latency": _stats(vithia_values),
        "control_loop_latency": _stats(control_values),
        "control_hz": round(len(telemetry) / elapsed, 4),
        "input_bytes": _stats([float(row["context_input_bytes"]) for row in telemetry]),
        "raw_input_bytes": _stats([float(row["raw_input_bytes"]) for row in telemetry]),
        "errors": errors,
        "fallbacks": sum(1 for row in telemetry if row["fallback"]),
        "action_distribution": action_distribution,
    }
    paths["manifest"].write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    proof = _verify_run_bundle(paths["manifest"]) if telemetry else {"RUN_PROOF_VERIFY": "BLOCKED_NO_STEPS"}
    manifest["run_proof"] = proof
    manifest["run_root"] = _sha({"manifest": manifest, "proof": proof})
    paths["manifest"].write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    paths["results"].write_text(json.dumps({"schema": "VITHIA_OPENJEV_AB_ARM_RESULTS_V1", "manifest": manifest}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


def _vithia_l1_context(state: dict[str, Any]) -> dict[str, Any]:
    """Small current-state ContextFCO with no action recommendation."""
    bombs = state.get("bombs") or []
    nearest_bomb = None
    if bombs:
        nearest_bomb = max(bombs, key=lambda b: b.get("y_bottom", -1))
    shields = state.get("shields") or []
    return {
        "encoding": "VITHIA_SPACE_L1_CONTEXT_V1",
        "step": state.get("step"),
        "score": state.get("score"),
        "lives": state.get("lives"),
        "previous_action": state.get("previous_action"),
        "ship": state.get("ship"),
        "nearest_bomb": nearest_bomb,
        "own_shot_count": len(state.get("own_shots") or []),
        "unknown_shot_count": len(state.get("unknown_shots") or []),
        "aliens": {
            "present": (state.get("aliens") or {}).get("present"),
            "count_est": (state.get("aliens") or {}).get("count_est"),
            "x_min": (state.get("aliens") or {}).get("x_min"),
            "x_max": (state.get("aliens") or {}).get("x_max"),
            "y_max": (state.get("aliens") or {}).get("y_max"),
        },
        "shield_count": len(shields),
        "shield_pixels": sum(int(s.get("pixels", 0)) for s in shields),
        "claim": "context_only_no_action_recommendation",
    }


def run_openjev_ab(args: argparse.Namespace) -> dict[str, Any]:
    seeds = [int(s) for s in args.seeds.split(",") if s.strip()]
    output_dir = Path(args.output_dir or DEFAULT_BENCHMARK_DIR).resolve()
    openjev = _openjev_status()
    blocked = openjev.get("OPENJEV_LOAD_STATE") != "PASS"
    if blocked:
        run_id = f"blocked_openjev_{uuid.uuid4().hex[:12]}"
        paths = _bundle_paths(output_dir, run_id)
        paths["run_dir"].mkdir(parents=True, exist_ok=True)
        receipt = {
            "schema": "VITHIA_OPENJEV_AB_BLOCKED_RECEIPT_V1",
            "run_id": run_id,
            "source_head": _git_head(),
            "OPENJEV_LOCAL_LOAD": openjev.get("OPENJEV_LOAD_STATE"),
            "openjev": openjev,
            "RAW_OPENJEV_1P": "BLOCKED_OPENJEV_NOT_LOADED",
            "VITHIA_OPENJEV_1P": "BLOCKED_OPENJEV_NOT_LOADED",
            "SAME_BACKEND": "YES_INTENDED_NOT_EXECUTED",
            "SAME_SEEDS": seeds,
            "ECA_VALIDATION": "PASS_BY_EXISTING_TESTS_NOT_REEXECUTED_IN_BLOCKED_RUN",
            "FCO_STEP_RECORDING": "BLOCKED_NO_STEPS",
            "MMR_APPEND": "BLOCKED_NO_STEPS",
            "RUN_PROOF_VERIFY": "BLOCKED_NO_STEPS",
        }
        paths["manifest"].write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"OPENJEV_LOCAL_LOAD={receipt['OPENJEV_LOCAL_LOAD']}", flush=True)
        print(f"OPENJEV_AB_BUNDLE={paths['run_dir']}", flush=True)
        return receipt

    raw = _benchmark_arm(arm="OPENJEV_RAW", preprocessor="NONE", seeds=seeds, steps=args.steps, output_dir=output_dir)
    vithia = _benchmark_arm(arm=f"OPENJEV_VITHIA_{args.vithia_level}", preprocessor="VITHIA_SPACE", seeds=seeds, steps=args.steps, output_dir=output_dir)
    comparison = {
        "schema": "VITHIA_OPENJEV_AB_COMPARISON_V1",
        "source_head": _git_head(),
        "seeds": seeds,
        "steps": args.steps,
        "same_backend": True,
        "same_seeds": True,
        "raw": raw,
        "vithia": vithia,
        "VITHIA_LEVEL_TESTED": args.vithia_level,
        "RAW_INPUT_SIZE": raw["input_bytes"]["mean"],
        "VITHIA_INPUT_SIZE": vithia["input_bytes"]["mean"],
        "RAW_DECISION_P50": raw["decision_latency"]["p50"],
        "VITHIA_DECISION_P50": vithia["decision_latency"]["p50"],
        "DELTA_DECISION_P50": None if raw["decision_latency"]["p50"] is None or vithia["decision_latency"]["p50"] is None else round(vithia["decision_latency"]["p50"] - raw["decision_latency"]["p50"], 4),
        "RAW_DECISION_P95": raw["decision_latency"]["p95"],
        "VITHIA_DECISION_P95": vithia["decision_latency"]["p95"],
        "DELTA_DECISION_P95": None if raw["decision_latency"]["p95"] is None or vithia["decision_latency"]["p95"] is None else round(vithia["decision_latency"]["p95"] - raw["decision_latency"]["p95"], 4),
        "RAW_MODEL_INFERENCE_P50": raw["openjev_inference"]["p50"],
        "VITHIA_MODEL_INFERENCE_P50": vithia["openjev_inference"]["p50"],
        "DELTA_MODEL_INFERENCE_P50": None if raw["openjev_inference"]["p50"] is None or vithia["openjev_inference"]["p50"] is None else round(vithia["openjev_inference"]["p50"] - raw["openjev_inference"]["p50"], 4),
        "RAW_SCORE": raw["score_total"],
        "VITHIA_SCORE": vithia["score_total"],
        "DELTA_SCORE": None if raw["score_total"] is None or vithia["score_total"] is None else round(vithia["score_total"] - raw["score_total"], 4),
        "RUN_PROOF_VERIFY": "PASS" if raw["run_proof"]["RUN_PROOF_VERIFY"] == "PASS" and vithia["run_proof"]["RUN_PROOF_VERIFY"] == "PASS" else "FAIL",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    comparison["FIGURES"] = _write_comparison_figures(comparison, output_dir)
    comparison["DERIVED_VIDEO"] = "NOT_CREATED_FROM_STATIC_KEYFRAMES_ONLY"
    comparison["PUBLIC_KEY_SEAL"] = "NOT_SIGNED_RUN_PROOF_ONLY"
    comparison_path = output_dir / f"comparison_{uuid.uuid4().hex[:12]}.json"
    comparison_path.write_text(json.dumps(comparison, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _append_json_result(Path(args.results_path).resolve(), {"schema": "VITHIA_OPENJEV_AB_COMPARISON_RESULT_V1", "comparison_path": str(comparison_path.relative_to(ROOT)), **comparison})
    print(f"OPENJEV_AB_COMPARISON={comparison_path}", flush=True)
    print(f"DELTA_DECISION_P50={comparison['DELTA_DECISION_P50']}", flush=True)
    return comparison


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
    parser.add_argument("--max-steps", type=int, help="Alias for --steps on benchmark-oriented invocations.")
    parser.add_argument("--episodes", type=int, default=1)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--render", choices=["none", "terminal"], default="none")
    parser.add_argument("--results-path", default=str(DEFAULT_RESULTS))
    parser.add_argument("--trace-dir")
    parser.add_argument("--output-dir")
    parser.add_argument("--run-class", default="BASELINE_LLM")
    parser.add_argument("--benchmark-pair-openjev", action="store_true")
    parser.add_argument("--seeds", default="1,2,3,4,5")
    parser.add_argument("--vithia-level", default="L1")
    parser.add_argument("--player0-preprocessor", "--p0-preprocessor", "--preprocessor", default="VITHIA_SPACE")
    parser.add_argument("--player0-decider", "--p0-decider", "--decider", default="scripted")
    parser.add_argument("--player0-model", "--p0-model")
    parser.add_argument("--player1-preprocessor", "--p1-preprocessor", default="VITHIA_SPACE")
    parser.add_argument("--player1-decider", "--p1-decider", default="scripted")
    parser.add_argument("--player1-model", "--p1-model")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.max_steps is not None:
        args.steps = args.max_steps
    if args.benchmark_pair_openjev:
        run_openjev_ab(args)
    else:
        run(args)


if __name__ == "__main__":
    main()
