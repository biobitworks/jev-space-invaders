#!/usr/bin/env python3
"""Local-only live 1P/2P demo server.

The browser is a thin control surface. Environment transitions happen only in
DemoController.step_once(), after every requested model action is validated.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import struct
import threading
import time
import urllib.request
import uuid
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import numpy as np

from src.actions import ACTIONS as ALE_ACTIONS
from src.envcfg import make_env
from src.perception import Perception, VERSION as PREPROCESSOR_VERSION

PZ_ACTIONS = ("NOOP", "FIRE", "UP", "RIGHT", "LEFT", "DOWN")
ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "demo" / "static"
DEFAULT_ROM_DIR = "/Volumes/magicBLACKbox/vithia-space-execution/pettingzoo-2p-venv/lib/python3.12/site-packages/ale_py/roms"


def digest(value: Any) -> str:
    if isinstance(value, bytes):
        raw = value
    elif isinstance(value, np.ndarray):
        raw = value.tobytes()
    else:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def png_bytes(frame: np.ndarray) -> bytes:
    rgb = frame.astype(np.uint8)
    height, width, _ = rgb.shape
    scanlines = b"".join(b"\x00" + rgb[row].tobytes() for row in range(height))
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(scanlines, 1)) + chunk(b"IEND", b"")


class OllamaDecider:
    def __init__(self, model: str, actions: tuple[str, ...], base_url: str = "http://127.0.0.1:11434") -> None:
        self.model = model
        self.actions = actions
        self.base_url = base_url.rstrip("/")

    def decide(self, state: dict[str, Any], mode: str) -> dict[str, Any]:
        question = {
            "mode": mode,
            "instructions": "Choose one legal action. Return only the JSON object.",
            "legal_actions": list(self.actions),
        }
        prompt = "QUESTION=" + json.dumps(question, sort_keys=True) + "\nSTATE=" + json.dumps(state, sort_keys=True)
        body = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": {"type": "object", "properties": {"action": {"type": "string", "enum": list(self.actions)}},
                        "required": ["action"], "additionalProperties": False},
            "options": {"temperature": 0, "seed": 0, "num_predict": 32},
        }
        started = time.perf_counter()
        try:
            req = urllib.request.Request(self.base_url + "/api/generate", data=json.dumps(body).encode(),
                                         headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=20) as response:
                payload = json.loads(response.read())
            answer = json.loads(payload.get("response") or "{}")
            requested = answer.get("action")
            valid = requested in self.actions
            return {
                "requested_action": requested,
                "executed_action": requested if valid else self.actions[0],
                "projected_plan": [requested] if valid else [],
                "confidence": None,
                "reason": "validated_model_action" if valid else "invalid_model_output_held_to_noop",
                "fallback": not valid,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                "backend": f"ollama:{payload.get('model') or self.model}",
                "model_call": True,
            }
        except Exception as exc:
            return {
                "requested_action": None,
                "executed_action": self.actions[0],
                "projected_plan": [],
                "confidence": None,
                "reason": f"model_request_failed:{type(exc).__name__}",
                "fallback": True,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                "backend": f"ollama:{self.model}",
                "model_call": True,
            }


class DemoController:
    def __init__(self, telemetry_dir: str | None = None) -> None:
        self.lock = threading.RLock()
        self.mode = "1P"
        self.seed = 3
        self.speed = 4.0
        self.preprocessor_on = True
        self.backtrace_depth = 3
        self.forecast_depth = 3
        self.models = {"1P": "qwen2.5:0.5b", "P0": "qwen2.5:0.5b", "P1": "longhorizon-liquid-230m:latest"}
        self.env = None
        self.obs = None
        self.info = {}
        self.pz_env = None
        self.pz_obs = {}
        self.pz_info = {}
        self.perception = Perception()
        self.pz_perception = {"first_0": Perception(), "second_0": Perception()}
        self.status = "idle"
        self.frame_index = 0
        self.decision_index = 0
        self.joint_step = 0
        self.score = 0.0
        self.rewards = {"first_0": 0.0, "second_0": 0.0}
        self.last_actions: dict[str, Any] = {}
        self.history: list[dict[str, Any]] = []
        self.current_frame = np.zeros((210, 160, 3), dtype=np.uint8)
        self.run_id = uuid.uuid4().hex
        self.telemetry_dir = Path(telemetry_dir or os.environ.get("LIVE_DEMO_TELEMETRY_DIR", "/tmp/vithia-live-demo"))
        self.telemetry_dir.mkdir(parents=True, exist_ok=True)
        self._play_thread: threading.Thread | None = None
        self.reset(self.seed)

    def _rom_dir(self) -> str | None:
        candidate = os.environ.get("ALE_ROM_DIR", DEFAULT_ROM_DIR)
        return candidate if Path(candidate, "space_invaders.bin").exists() else None

    def _close_envs(self) -> None:
        for env in (self.env, self.pz_env):
            if env is not None:
                try:
                    env.close()
                except Exception:
                    pass
        self.env = self.pz_env = None

    def reset(self, seed: int | None = None) -> dict[str, Any]:
        with self.lock:
            self._stop_thread()
            self._close_envs()
            self.seed = int(self.seed if seed is None else seed)
            self.run_id = uuid.uuid4().hex
            self.frame_index = self.decision_index = self.joint_step = 0
            self.score = 0.0
            self.rewards = {"first_0": 0.0, "second_0": 0.0}
            self.last_actions = {}
            self.history = []
            self.perception.reset()
            for p in self.pz_perception.values():
                p.reset()
            if self.mode == "1P":
                self.env = make_env()
                self.obs, self.info = self.env.reset(seed=self.seed)
                self.current_frame = self.obs
            else:
                from pettingzoo.atari import space_invaders_v2
                rom_dir = self._rom_dir()
                if not rom_dir:
                    raise RuntimeError("PETTINGZOO_ROM_GATE_BLOCKED")
                self.pz_env = space_invaders_v2.parallel_env(auto_rom_install_path=rom_dir)
                self.pz_obs, self.pz_info = self.pz_env.reset(seed=self.seed)
                self.current_frame = self.pz_obs[self.pz_env.agents[0]]
            self.status = "paused"
            self._write({"event": "RESET", "mode": self.mode, "seed": self.seed, "run_id": self.run_id})
            return self.state()

    def _stop_thread(self) -> None:
        self.status = "paused" if self.status != "stopped" else self.status
        self._play_thread = None

    def play(self) -> dict[str, Any]:
        with self.lock:
            if self.env is None and self.pz_env is None:
                self.reset(self.seed)
            self.status = "playing"
            if self._play_thread is None or not self._play_thread.is_alive():
                self._play_thread = threading.Thread(target=self._loop, daemon=True)
                self._play_thread.start()
            return self.state()

    def _loop(self) -> None:
        while True:
            with self.lock:
                if self.status != "playing":
                    return
                self.step_once()
                interval = max(0.05, 1.0 / max(self.speed, 0.1))
            time.sleep(interval)

    def pause(self) -> dict[str, Any]:
        with self.lock:
            self.status = "paused"
            return self.state()

    def stop(self) -> dict[str, Any]:
        with self.lock:
            self.status = "stopped"
            return self.state()

    def set_mode(self, mode: str) -> dict[str, Any]:
        if mode not in ("1P", "2P"):
            raise ValueError("mode must be 1P or 2P")
        with self.lock:
            self.status = "paused"
            self.mode = mode
            return self.reset(self.seed)

    def set_model(self, slot: str, model: str) -> dict[str, Any]:
        with self.lock:
            self.status = "paused"
            self.models[slot] = model
            self._write({"event": "ModelSwitchOccurrence", "slot": slot, "new_model": model, "run_id": self.run_id})
            return self.state()

    def configure(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            self.preprocessor_on = bool(payload.get("preprocessor_on", self.preprocessor_on))
            self.backtrace_depth = max(0, int(payload.get("backtrace_depth", self.backtrace_depth)))
            self.forecast_depth = max(0, int(payload.get("forecast_depth", self.forecast_depth)))
            self.speed = max(0.1, float(payload.get("speed", self.speed)))
            return self.state()

    def _preprocess(self, frame: np.ndarray, info: dict[str, Any], step: int, prev: str) -> tuple[dict[str, Any], dict[str, Any]]:
        if not self.preprocessor_on:
            return {"encoding": "preprocessor_off", "step": step}, {"fallback": False, "version": "OFF"}
        started = time.perf_counter()
        try:
            state = self.perception.observe(frame, lives=int(info.get("lives", 0)), score=self.score, step=step, prev_action=prev)
            return state, {"fallback": False, "version": PREPROCESSOR_VERSION, "latency_ms": round((time.perf_counter() - started) * 1000, 2)}
        except Exception as exc:
            return {"encoding": "preprocessor_fallback", "step": step, "error": type(exc).__name__}, {"fallback": True, "version": PREPROCESSOR_VERSION, "latency_ms": round((time.perf_counter() - started) * 1000, 2)}

    def step_once(self) -> dict[str, Any]:
        if self.mode == "1P":
            return self._step_1p()
        return self._step_2p()

    def _step_1p(self) -> dict[str, Any]:
        if self.env is None:
            return self.state()
        prev = self.last_actions.get("1P", "NOOP")
        context, prep = self._preprocess(self.obs, self.info, self.decision_index, prev)
        decision = OllamaDecider(self.models["1P"], ALE_ACTIONS).decide(context, "1P_ALE")
        action = decision["executed_action"]
        next_obs, reward, term, trunc, info = self.env.step(ALE_ACTIONS.index(action))
        self.obs, self.info = next_obs, info
        self.current_frame = next_obs
        self.score += float(reward)
        row = {"timestamp": time.time(), "run_id": self.run_id, "mode": "1P", "seed": self.seed,
               "decision_index": self.decision_index, "environment_frame": int(info.get("episode_frame_number", self.frame_index)),
               "state_hash": digest(context), "preprocessor": prep["version"], "preprocessor_output_hash": digest(context),
               "preprocessing_latency_ms": prep.get("latency_ms", 0), "decider_backend": decision["backend"],
               "requested_action": decision["requested_action"], "executed_action": action,
               "projected_plan": decision["projected_plan"], "latency_ms": decision["latency_ms"], "reward": float(reward),
               "score": self.score, "lives": int(info.get("lives", 0)), "fallback": decision["fallback"],
               "reason": decision["reason"], "preprocessor_fallback": prep["fallback"], "env_advanced": True}
        self._write(row)
        self.history.append(row)
        self.last_actions["1P"] = action
        self.decision_index += 1
        self.frame_index += 1
        if term or trunc:
            self.status = "stopped"
        return self.state()

    def _step_2p(self) -> dict[str, Any]:
        if self.pz_env is None:
            return self.state()
        actions, players = {}, {}
        for agent in tuple(self.pz_env.agents):
            frame = self.pz_obs[agent]
            context, prep = self._preprocess(frame, self.pz_info.get(agent, {}), self.joint_step, self.last_actions.get(agent, "NOOP"))
            # Keep the seat-local state explicit; no action recommendation is added by preprocessing.
            context = dict(context)
            context["seat"] = agent
            decision = OllamaDecider(self.models["P0" if agent == "first_0" else "P1"], PZ_ACTIONS).decide(context, "2P_PETTINGZOO")
            actions[agent] = PZ_ACTIONS.index(decision["executed_action"])
            players[agent] = {"preprocessor": prep["version"], "preprocessor_output_hash": digest(context),
                              "decider": decision["backend"], "requested_action": decision["requested_action"],
                              "executed_action": decision["executed_action"], "projected_plan": decision["projected_plan"],
                              "latency_ms": decision["latency_ms"], "fallback": decision["fallback"],
                              "state_hash": digest(context), "preprocessor_fallback": prep["fallback"]}
        next_obs, rewards, terms, truncs, infos = self.pz_env.step(actions)
        self.pz_obs, self.pz_info = next_obs, infos
        self.current_frame = next_obs.get("first_0", self.current_frame)
        self.rewards = {a: float(rewards.get(a, 0.0)) for a in ("first_0", "second_0")}
        row = {"timestamp": time.time(), "run_id": self.run_id, "mode": "2P", "seed": self.seed,
               "joint_step": self.joint_step, "environment_state_hash": digest({a: digest(o) for a, o in next_obs.items()}),
               "player0": players.get("first_0"), "player1": players.get("second_0"),
               "joint_transition_executed": True, "env_advanced": True}
        self._write(row)
        self.history.append(row)
        self.last_actions = {a: PZ_ACTIONS[idx] for a, idx in actions.items()}
        self.joint_step += 1
        self.decision_index += 2
        self.frame_index += 1
        if not self.pz_env.agents or all(terms.get(a) or truncs.get(a) for a in terms):
            self.status = "stopped"
        return self.state()

    def _write(self, row: dict[str, Any]) -> None:
        path = self.telemetry_dir / f"{self.run_id}.jsonl"
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")

    def models_available(self) -> list[dict[str, Any]]:
        try:
            with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=3) as r:
                rows = json.loads(r.read()).get("models", [])
            return [{"name": row.get("name"), "digest": row.get("digest"), "provider": "OLLAMA"} for row in rows]
        except Exception as exc:
            return [{"error": type(exc).__name__, "provider": "OLLAMA"}]

    def integrations(self) -> dict[str, Any]:
        models = self.models_available()
        tags = {m.get("name") for m in models}
        try:
            with urllib.request.urlopen("http://127.0.0.1:8484/health", timeout=2) as r:
                health = json.loads(r.read())
            ollarma = {"status": "PARTIAL" if health.get("status") == "degraded" else "PASS", "reason": health.get("startup_readiness", {}).get("model_availability", {}).get("reason_code")}
        except Exception as exc:
            ollarma = {"status": "BLOCKED", "reason": type(exc).__name__}
        return {
            "OLLAMA": {"status": "PASS" if tags else "BLOCKED", "1P": bool(tags), "2P": bool(tags), "models": sorted(tags), "reason": "local tags discovered" if tags else "no models"},
            "OLLARMA": {**ollarma, "1P": False, "2P": False, "reason": ollarma.get("reason") or "runtime reachable; advisory only"},
            "SYSTEM_ONE": {"status": "NOT_CONFIGURED", "1P": False, "2P": False, "reason": "no live endpoint configured"},
            "TENKI": {"status": "DEFERRED", "1P": False, "2P": False, "reason": "not used by local demo"},
            "MITOSIS_LABS": {"status": "DEFERRED", "1P": False, "2P": False, "reason": "not used by local demo"},
            "OPENJEV": {"status": "NOT_TESTED", "1P": False, "2P": False, "reason": "historical stand-in is not a counted live demo backend"},
            "LIQUID_AI": {"status": "PASS" if "longhorizon-liquid-230m:latest" in tags else "NOT_CONFIGURED", "1P": "longhorizon-liquid-230m:latest" in tags, "2P": "longhorizon-liquid-230m:latest" in tags, "reason": "local Ollama tag"},
            "VITHIA_PREPROCESSOR": {"status": "PASS", "1P": True, "2P": True, "reason": PREPROCESSOR_VERSION},
        }

    def state(self) -> dict[str, Any]:
        with self.lock:
            return {"mode": self.mode, "status": self.status, "seed": self.seed, "run_id": self.run_id,
                    "frame_index": self.frame_index, "decision_index": self.decision_index, "joint_step": self.joint_step,
                    "score": self.score, "rewards": self.rewards, "lives": int(self.info.get("lives", 0)) if self.mode == "1P" else None,
                    "last_actions": self.last_actions, "history": self.history[-30:], "models": self.models,
                    "preprocessor_on": self.preprocessor_on, "preprocessor_version": PREPROCESSOR_VERSION,
                    "backtrace_depth": self.backtrace_depth, "forecast_depth": self.forecast_depth, "speed": self.speed,
                    "frame_hash": digest(self.current_frame.tobytes()), "frame_url": "/frame.png", "telemetry_dir": str(self.telemetry_dir)}


class Handler(BaseHTTPRequestHandler):
    controller: DemoController
    server_version = "VithiaLiveDemo/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _send(self, status: int, body: bytes, content_type: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj: Any, status: int = 200) -> None:
        self._send(status, json.dumps(obj, sort_keys=True).encode())

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
        elif parsed.path == "/app.js":
            self._send(200, (STATIC / "app.js").read_bytes(), "text/javascript; charset=utf-8")
        elif parsed.path == "/styles.css":
            self._send(200, (STATIC / "styles.css").read_bytes(), "text/css; charset=utf-8")
        elif parsed.path == "/frame.png":
            self._send(200, png_bytes(self.controller.current_frame), "image/png")
        elif parsed.path == "/api/state":
            self._json(self.controller.state())
        elif parsed.path == "/api/models":
            self._json({"models": self.controller.models_available()})
        elif parsed.path == "/api/integrations":
            self._json(self.controller.integrations())
        else:
            self._json({"error": "not_found"}, 404)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            if parsed.path == "/api/play": result = self.controller.play()
            elif parsed.path == "/api/pause": result = self.controller.pause()
            elif parsed.path == "/api/stop": result = self.controller.stop()
            elif parsed.path == "/api/step": result = self.controller.step_once()
            elif parsed.path == "/api/reset": result = self.controller.reset(payload.get("seed", self.controller.seed))
            elif parsed.path == "/api/mode": result = self.controller.set_mode(payload.get("mode"))
            elif parsed.path == "/api/model": result = self.controller.set_model(payload.get("slot", "1P"), payload["model"])
            elif parsed.path == "/api/config": result = self.controller.configure(payload)
            else: self._json({"error": "not_found"}, 404); return
            self._json(result)
        except Exception as exc:
            self._json({"error": type(exc).__name__, "detail": str(exc)}, 400)


def serve(host: str = "127.0.0.1", port: int = 8788, telemetry_dir: str | None = None) -> ThreadingHTTPServer:
    controller = DemoController(telemetry_dir)
    Handler.controller = controller
    server = ThreadingHTTPServer((host, port), Handler)
    server.controller = controller  # type: ignore[attr-defined]
    return server


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8788)
    parser.add_argument("--telemetry-dir")
    args = parser.parse_args()
    httpd = serve(args.host, args.port, args.telemetry_dir)
    print(f"LIVE_DEMO_URL=http://{args.host}:{args.port}", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.controller._close_envs()
        httpd.server_close()
