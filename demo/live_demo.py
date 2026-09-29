#!/usr/bin/env python3
"""Local Vithia Space demo with per-seat preprocessors and deciders."""
from __future__ import annotations

import hashlib
import json
import os
import struct
import threading
import time
import urllib.request
import uuid
import zlib
from dataclasses import asdict, dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import numpy as np

from src.actions import ACTIONS as ALE_ACTIONS
from src.eca_actions import decompose
from src.envcfg import make_env
from src.perception import Perception, VERSION as PREPROCESSOR_VERSION

PZ_ACTIONS = ("NOOP", "FIRE", "UP", "RIGHT", "LEFT", "DOWN")
ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "demo" / "static"
DEFAULT_ROM_DIR = "/Volumes/magicBLACKbox/vithia-space-execution/pettingzoo-2p-venv/lib/python3.12/site-packages/ale_py/roms"


def digest(value: Any) -> str:
    if isinstance(value, bytes): raw = value
    elif isinstance(value, np.ndarray): raw = value.tobytes()
    else: raw = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def png_bytes(frame: np.ndarray) -> bytes:
    rgb = frame.astype(np.uint8); h, w, _ = rgb.shape
    scanlines = b"".join(b"\x00" + rgb[row].tobytes() for row in range(h))
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xffffffff)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(scanlines, 1)) + chunk(b"IEND", b"")


@dataclass
class PlayerSeatConfig:
    seat_id: str
    preprocessor: str = "VITHIA_SPACE"
    decision_layer: str = "SYSTEM_ONE"
    decider_provider: str = "OLLAMA"
    decider_backend: str = "qwen2.5:0.5b"
    exact_model: str = "qwen2.5:0.5b"
    fallback_policy: str = "NOOP"
    history_depth: int = 3
    forecast_depth: int = 3

    def public(self) -> dict[str, Any]: return asdict(self)


@dataclass
class ProviderRecord:
    provider_id: str
    display_name: str
    role: str
    runtime: str | None
    exact_model: str | None
    available: bool
    configured: bool
    authenticated: bool
    live_probe: str
    supports_1p: bool
    supports_2p: bool
    reason: str

    def public(self) -> dict[str, Any]: return asdict(self)


def post_json(url: str, body: dict[str, Any], timeout: float = 20.0) -> dict[str, Any]:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as response: return json.loads(response.read())


class Decider:
    def __init__(self, provider: str, backend: str, actions: tuple[str, ...]) -> None: self.provider, self.backend, self.actions = provider, backend, actions
    def decide(self, state: dict[str, Any], mode: str, previous: str) -> dict[str, Any]: raise NotImplementedError


class ScriptedDecider(Decider):
    def decide(self, state: dict[str, Any], mode: str, previous: str) -> dict[str, Any]:
        action = self.actions[int(state.get("step", 0)) % len(self.actions)]
        return {"requested_action": action, "executed_action": action, "fallback": False, "latency_ms": 0.01, "backend": "scripted:baseline", "model_call": False, "reason": "non_model_reference"}


class HTTPChoiceDecider(Decider):
    def __init__(self, provider: str, backend: str, actions: tuple[str, ...], url: str, model: str, system_one: bool = False) -> None:
        super().__init__(provider, backend, actions); self.url, self.model, self.system_one = url.rstrip("/"), model, system_one

    def decide(self, state: dict[str, Any], mode: str, previous: str) -> dict[str, Any]:
        started = time.perf_counter(); question = {"mode": mode, "instructions": "Choose one legal action. Return only the JSON object.", "legal_actions": list(self.actions)}
        try:
            if self.system_one:
                body = {"state": state, "model": self.model, "questions": {"move": {"type": "choice", "instructions": question["instructions"], "criteria": {a: a for a in self.actions}}}}
                payload = post_json(self.url + "/v1/systemone", body)
                requested = (((payload.get("answers") or {}).get("move") or {}).get("choice"))
            else:
                body = {"model": self.model, "prompt": "QUESTION=" + json.dumps(question, sort_keys=True) + "\nSTATE=" + json.dumps(state, sort_keys=True), "stream": False, "format": {"type": "object", "properties": {"action": {"type": "string", "enum": list(self.actions)}}, "required": ["action"], "additionalProperties": False}, "options": {"temperature": 0, "seed": 0, "num_predict": 32}}
                payload = post_json(self.url + "/api/generate", body)
                try:
                    answer = json.loads(payload.get("response") or "{}")
                    requested = answer.get("action") or answer.get("choice")
                except (TypeError, ValueError): requested = None
            valid = requested in self.actions; fallback = "NOOP" if "NOOP" in self.actions else previous
            return {"requested_action": requested, "executed_action": requested if valid else fallback, "projected_plan": [requested] if valid else [], "confidence": None, "trace_id": uuid.uuid4().hex, "fallback": not valid, "latency_ms": round((time.perf_counter() - started) * 1000, 2), "backend": f"{self.provider.lower()}:{payload.get('model') or self.model}", "model_call": True, "reason": "validated_model_action" if valid else "invalid_model_output_fail_closed"}
        except Exception as exc:
            fallback = "NOOP" if "NOOP" in self.actions else previous
            return {"requested_action": None, "executed_action": fallback, "projected_plan": [], "confidence": None, "trace_id": uuid.uuid4().hex, "fallback": True, "latency_ms": round((time.perf_counter() - started) * 1000, 2), "backend": f"{self.provider.lower()}:{self.model}", "model_call": True, "reason": f"provider_unavailable:{type(exc).__name__}"}


class SystemOneBackend(HTTPChoiceDecider):
    """Stable decision interface shared by local and future hosted System-One."""
    def __init__(self, provider: str, backend: str, actions: tuple[str, ...], url: str, model: str) -> None:
        super().__init__(provider, backend, actions, url, model, True)


class OpenJEVLocalSystemOne(SystemOneBackend):
    pass


class JEVApiSystemOne(SystemOneBackend):
    pass


class ProviderRegistry:
    def __init__(self) -> None:
        self.ollama_url = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        self.liquid_url = os.environ.get("LIQUID_LOCAL_URL", self.ollama_url)
        self.openjev_url = os.environ.get("OPENJEV_BASE_URL", "http://127.0.0.1:8765")
        self.models = self._ollama_models()

    def _ollama_models(self) -> list[dict[str, Any]]:
        try:
            with urllib.request.urlopen(self.ollama_url.rstrip("/") + "/api/tags", timeout=3) as response:
                return [{"name": m.get("name"), "digest": m.get("digest"), "provider": "OLLAMA"} for m in json.loads(response.read()).get("models", [])]
        except Exception: return []

    def _probe(self, url: str) -> tuple[str, str]:
        try:
            with urllib.request.urlopen(url, timeout=2) as response: return "PASS", f"HTTP_{response.status}"
        except Exception as exc: return "BLOCKED", type(exc).__name__

    def records(self) -> list[ProviderRecord]:
        tags = {m["name"] for m in self.models if m.get("name")}; ollama = bool(tags); liquid = "longhorizon-liquid-230m:latest" in tags
        manifest = ROOT / "evidence/openjev/RUNTIME_MANIFEST.json"; openjev_loaded = False
        if manifest.exists():
            try: openjev_loaded = json.loads(manifest.read_text()).get("OPENJEV_LOADED") == "YES"
            except json.JSONDecodeError: pass
        openjev_probe, openjev_reason = self._probe(self.openjev_url + "/health")
        tenki = bool(os.environ.get("TENKI_API_KEY") or os.environ.get("TENKI_AUTH_TOKEN")); mitosis = bool(os.environ.get("MI_API_KEY") or os.environ.get("MITOSIS_API_KEY"))
        return [
            ProviderRecord("SYSTEM_ONE", "System-One", "DECIDER", "local interface", "openjev" if openjev_loaded else None, openjev_loaded, True, openjev_loaded, openjev_probe if openjev_loaded else "NOT_TESTED", True, True, "stable interface; local backend is OpenJEV" if openjev_loaded else "OPENJEV_LOCAL not resident"),
            ProviderRecord("OPENJEV_LOCAL", "OpenJEV Local", "DECIDER", "MLX/local HTTP", "openjev" if openjev_loaded else None, openjev_loaded, openjev_loaded, openjev_loaded, openjev_probe if openjev_loaded else "NOT_TESTED", True, True, openjev_reason if not openjev_loaded else "runtime manifest loaded"),
            ProviderRecord("JEV_API_REMOTE", "JEV API Remote", "DECIDER", "HTTPS", None, False, bool(os.environ.get("TYPESAFE_API_KEY")), bool(os.environ.get("TYPESAFE_API_KEY")), "NOT_TESTED", True, True, "future API path; no remote request made"),
            ProviderRecord("OLLAMA", "Ollama", "DECIDER", "Ollama HTTP", None, ollama, True, ollama, "PASS" if ollama else "BLOCKED", True, True, "dynamically discovered local tags" if ollama else "no local tags"),
            ProviderRecord("LIQUID_LOCAL", "Liquid Local", "DECIDER", "Ollama-compatible HTTP", "longhorizon-liquid-230m:latest" if liquid else None, liquid, liquid, liquid, "PASS" if liquid else "BLOCKED", True, True, "exact local Liquid tag discovered" if liquid else "Liquid local tag unavailable"),
            ProviderRecord("LIQUID_API", "Liquid API", "DECIDER", "HTTPS", os.environ.get("LIQUID_API_MODEL"), False, bool(os.environ.get("LIQUID_API_KEY")), False, "NOT_TESTED", True, True, "API credentials/model not configured"),
            ProviderRecord("TENKI", "Tenki", "DECIDER", "HTTPS", os.environ.get("TENKI_MODEL"), tenki, tenki, False, "NOT_TESTED", True, True, "credentials present but no live probe" if tenki else "TENKI_API_KEY/TENKI_AUTH_TOKEN absent"),
            ProviderRecord("MITOSIS_LABS", "Mitosis Labs", "CONTEXT_PROVIDER", "HTTPS", None, mitosis, mitosis, False, "NOT_TESTED", False, False, "memory/context provider; not a decision model"),
            ProviderRecord("SCRIPTED_BASELINE", "Scripted Baseline", "NON_MODEL_REFERENCE", "stdlib", "scripted-policy", True, True, True, "PASS", True, True, "non-model reference"),
        ]

    def decider(self, cfg: PlayerSeatConfig, actions: tuple[str, ...]) -> Decider:
        p = cfg.decider_provider; b = cfg.decider_backend
        if p == "SCRIPTED_BASELINE": return ScriptedDecider(p, b, actions)
        if p == "OLLAMA": return HTTPChoiceDecider(p, b, actions, self.ollama_url, cfg.exact_model)
        if p == "LIQUID_LOCAL": return HTTPChoiceDecider(p, b, actions, self.liquid_url, cfg.exact_model)
        if p == "OPENJEV_LOCAL" or (p == "SYSTEM_ONE" and b == "OPENJEV_LOCAL"): return OpenJEVLocalSystemOne(p, b, actions, self.openjev_url, cfg.exact_model or "openjev")
        urls = {"JEV_API_REMOTE": os.environ.get("JEV_API_URL", "https://api.typesafe.ai"), "TENKI": os.environ.get("TENKI_API_URL", "http://127.0.0.1:9"), "MITOSIS_LABS": os.environ.get("MITOSIS_API_URL", "http://127.0.0.1:9"), "LIQUID_API": os.environ.get("LIQUID_API_URL", "http://127.0.0.1:9")}
        if p == "JEV_API_REMOTE": return JEVApiSystemOne(p, b, actions, urls[p], cfg.exact_model or b)
        return HTTPChoiceDecider(p, b, actions, urls.get(p, "http://127.0.0.1:9"), cfg.exact_model or b, True)


class DemoController:
    def __init__(self, telemetry_dir: str | None = None) -> None:
        self.lock, self.step_lock = threading.RLock(), threading.Lock(); self.mode, self.seed, self.speed = "1P", 3, 4.0; self.registry = ProviderRegistry()
        self.seats = {"PLAYER_0": PlayerSeatConfig("PLAYER_0", decision_layer="SYSTEM_ONE", decider_provider="SYSTEM_ONE", decider_backend="OPENJEV_LOCAL", exact_model="openjev"), "PLAYER_1": PlayerSeatConfig("PLAYER_1", decision_layer="SYSTEM_ONE", decider_provider="LIQUID_LOCAL", decider_backend="longhorizon-liquid-230m:latest", exact_model="longhorizon-liquid-230m:latest")}
        self.env = self.obs = self.pz_env = None; self.info, self.pz_obs, self.pz_info = {}, {}, {}; self.perceptions = {"PLAYER_0": Perception(), "PLAYER_1": Perception()}; self.status, self.frame_index, self.decision_index, self.joint_step = "idle", 0, 0, 0; self.score, self.rewards, self.last_actions, self.history = 0.0, {"first_0": 0.0, "second_0": 0.0}, {}, []; self.current_frame = np.zeros((210, 160, 3), dtype=np.uint8); self.run_id, self.generation_id, self.episode_id = uuid.uuid4().hex, 0, uuid.uuid4().hex; self.telemetry_dir = Path(telemetry_dir or os.environ.get("LIVE_DEMO_TELEMETRY_DIR", "/tmp/vithia-live-demo")); self.telemetry_dir.mkdir(parents=True, exist_ok=True); self._play_thread = None; self.reset(self.seed)

    def _rom_dir(self) -> str | None:
        candidate = os.environ.get("ALE_ROM_DIR", DEFAULT_ROM_DIR); return candidate if Path(candidate, "space_invaders.bin").exists() else None
    def _close_envs(self) -> None:
        for env in (self.env, self.pz_env):
            if env is not None:
                try: env.close()
                except Exception: pass
        self.env = self.pz_env = None
    def _invalidate(self, status: str | None = None) -> None:
        with self.lock:
            self.generation_id += 1
            if status: self.status = status
    def reset(self, seed: int | None = None) -> dict[str, Any]:
        self._invalidate("paused")
        with self.step_lock:
            with self.lock:
                self._close_envs(); self.seed = int(self.seed if seed is None else seed); self.run_id = uuid.uuid4().hex; self.episode_id = uuid.uuid4().hex; self.frame_index = self.decision_index = self.joint_step = 0; self.score = 0.0; self.rewards = {"first_0": 0.0, "second_0": 0.0}; self.last_actions = {}; self.history = []
                for p in self.perceptions.values(): p.reset()
                if self.mode == "1P": self.env = make_env(); self.obs, self.info = self.env.reset(seed=self.seed); self.current_frame = self.obs
                else:
                    from pettingzoo.atari import space_invaders_v2
                    rom_dir = self._rom_dir()
                    if not rom_dir: raise RuntimeError("PETTINGZOO_ROM_GATE_BLOCKED")
                    self.pz_env = space_invaders_v2.parallel_env(auto_rom_install_path=rom_dir); self.pz_obs, self.pz_info = self.pz_env.reset(seed=self.seed); self.current_frame = self.pz_obs[self.pz_env.agents[0]]
                self.status = "paused"; self._write({"event": "RESET", "mode": self.mode, "seed": self.seed, "run_id": self.run_id, "generation_id": self.generation_id})
        return self.state()
    def play(self) -> dict[str, Any]:
        with self.lock:
            if self.env is None and self.pz_env is None: self.reset(self.seed)
            self.status = "playing"
            if self._play_thread is None or not self._play_thread.is_alive(): self._play_thread = threading.Thread(target=self._loop, daemon=True); self._play_thread.start()
        return self.state()
    def _loop(self) -> None:
        while True:
            with self.lock:
                if self.status != "playing": return
                interval = max(0.05, 1.0 / max(self.speed, 0.1))
            self.step_once(); time.sleep(interval)
    def pause(self) -> dict[str, Any]: self._invalidate("paused"); return self.state()
    def stop(self) -> dict[str, Any]: self._invalidate("stopped"); return self.state()
    def set_mode(self, mode: str) -> dict[str, Any]:
        if mode not in ("1P", "2P"): raise ValueError("mode must be 1P or 2P")
        with self.lock: self.mode = mode
        return self.reset(self.seed)
    def set_seat(self, seat_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if seat_id not in self.seats: raise ValueError("unknown seat")
        self._invalidate("paused")
        with self.lock:
            cfg = self.seats[seat_id]
            for key in ("preprocessor", "decision_layer", "decider_provider", "decider_backend", "exact_model", "fallback_policy"):
                if key in payload: setattr(cfg, key, str(payload[key]))
            for key in ("history_depth", "forecast_depth"):
                if key in payload: setattr(cfg, key, max(0, int(payload[key])))
            self._write({"event": "SeatConfigChanged", "seat_id": seat_id, "config": cfg.public(), "generation_id": self.generation_id})
        return self.state()
    def configure(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self.lock: self.speed = max(0.1, float(payload.get("speed", self.speed)))
        return self.state()
    def _preprocess(self, seat_id: str, frame: np.ndarray, info: dict[str, Any], step: int, prev: str) -> tuple[dict[str, Any], dict[str, Any]]:
        cfg = self.seats[seat_id]; started = time.perf_counter(); input_hash = digest(frame)
        if cfg.preprocessor == "NONE": context, actual = {"encoding": "NONE", "step": step, "previous_action": prev}, "NONE"
        else:
            try: context, actual = self.perceptions[seat_id].observe(frame, lives=int(info.get("lives", 0)), score=self.score, step=step, prev_action=prev), PREPROCESSOR_VERSION
            except Exception as exc: context, actual = {"encoding": "VITHIA_SPACE_FALLBACK", "step": step, "error": type(exc).__name__}, "VITHIA_SPACE_FALLBACK"
        return context, {"requested": cfg.preprocessor, "actual": actual, "latency_ms": round((time.perf_counter() - started) * 1000, 2), "input_hash": input_hash, "output_hash": digest(context), "fallback": actual.endswith("FALLBACK")}
    def _seat_decision(self, seat_id: str, context: dict[str, Any], mode: str, previous: str, generation: int, actions: tuple[str, ...]) -> dict[str, Any]:
        cfg = self.seats[seat_id]; result = self.registry.decider(cfg, actions).decide(context, mode, previous); result.update({"seat_id": seat_id, "generation_id": generation, "requested_backend": f"{cfg.decider_provider}/{cfg.decider_backend}", "decision_layer": cfg.decision_layer, "decider_provider": cfg.decider_provider, "decider_backend": cfg.decider_backend, "exact_model": cfg.exact_model}); return result
    def step_once(self) -> dict[str, Any]:
        if not self.step_lock.acquire(blocking=False): return self.state()
        try:
            with self.lock:
                if self.status not in ("playing", "paused"): return self.state()
                mode, generation, episode = self.mode, self.generation_id, self.episode_id
                if mode == "1P": frame, info, prev = self.obs, self.info, self.last_actions.get("PLAYER_0", "NOOP")
                else: frame, info, prev = None, None, "NOOP"
            return self._compute_1p(frame, info, prev, generation, episode) if mode == "1P" else self._compute_2p(generation, episode)
        finally: self.step_lock.release()
    def _valid_epoch(self, generation: int, episode: str, mode: str) -> bool: return self.generation_id == generation and self.episode_id == episode and self.mode == mode and self.status in ("playing", "paused")
    def _compute_1p(self, frame: np.ndarray, info: dict[str, Any], prev: str, generation: int, episode: str) -> dict[str, Any]:
        context, prep = self._preprocess("PLAYER_0", frame, info, self.decision_index, prev); context["seat"] = "PLAYER_0"; decision = self._seat_decision("PLAYER_0", context, "1P_ALE", prev, generation, ALE_ACTIONS)
        with self.lock:
            if not self._valid_epoch(generation, episode, "1P"): self._write({"event": "DISCARD_STALE_RESULT", "generation_id": generation, "seat_id": "PLAYER_0"}); return self.state()
            next_obs, reward, term, trunc, info2 = self.env.step(ALE_ACTIONS.index(decision["executed_action"])); self.obs, self.info, self.current_frame = next_obs, info2, next_obs; self.score += float(reward)
            move, fire = decompose(decision["executed_action"]); row = {"timestamp": time.time(), "run_id": self.run_id, "mode": "1P", "seat_id": "PLAYER_0", "decision_index": self.decision_index, "generation_id": generation, "environment_frame": int(info2.get("episode_frame_number", self.frame_index)), "preprocessor_requested": prep["requested"], "preprocessor_actual": prep["actual"], "preprocessor_latency_ms": prep["latency_ms"], "preprocessor_input_hash": prep["input_hash"], "preprocessor_output_hash": prep["output_hash"], "eca_move": move, "eca_fire": fire, "eca_round_trip": decision["executed_action"], "environment_action_executed": True, **decision, "reward": float(reward), "score": self.score, "lives": int(info2.get("lives", 0)), "env_advanced": True}; self._record(row, decision["executed_action"]); self.frame_index += 1
            if term or trunc: self.status = "stopped"
            return self.state()
    def _compute_2p(self, generation: int, episode: str) -> dict[str, Any]:
        with self.lock: agents = tuple(self.pz_env.agents) if self.pz_env else (); snapshots = [(a, self.pz_obs[a], self.pz_info.get(a, {}), self.last_actions.get(a, "NOOP")) for a in agents]
        actions, players = {}, {}
        for agent, frame, info, prev in snapshots:
            seat_id = "PLAYER_0" if agent == "first_0" else "PLAYER_1"; context, prep = self._preprocess(seat_id, frame, info, self.joint_step, prev); context["seat"] = seat_id; decision = self._seat_decision(seat_id, context, "2P_PETTINGZOO", prev, generation, PZ_ACTIONS); actions[agent] = PZ_ACTIONS.index(decision["executed_action"]); players[agent] = {"preprocessor_requested": prep["requested"], "preprocessor_actual": prep["actual"], "preprocessor_latency_ms": prep["latency_ms"], "preprocessor_input_hash": prep["input_hash"], "preprocessor_output_hash": prep["output_hash"], **decision}
        with self.lock:
            if not self._valid_epoch(generation, episode, "2P"): self._write({"event": "DISCARD_STALE_RESULT", "generation_id": generation, "seat_ids": [p[0] for p in snapshots]}); return self.state()
            next_obs, rewards, terms, truncs, infos = self.pz_env.step(actions); self.pz_obs, self.pz_info = next_obs, infos; self.current_frame = next_obs.get("first_0", self.current_frame); self.rewards = {a: float(rewards.get(a, 0.0)) for a in ("first_0", "second_0")}; row = {"timestamp": time.time(), "run_id": self.run_id, "mode": "2P", "seed": self.seed, "joint_step": self.joint_step, "generation_id": generation, "player0": players.get("first_0"), "player1": players.get("second_0"), "joint_transition_executed": True, "env_advanced": True, "environment_state_hash": digest({a: digest(o) for a, o in next_obs.items()})}; self._record(row, None, 0); self.last_actions = {a: PZ_ACTIONS[idx] for a, idx in actions.items()}; self.joint_step += 1; self.decision_index += len(actions); self.frame_index += 1
            if not self.pz_env.agents or all(terms.get(a) or truncs.get(a) for a in terms): self.status = "stopped"
            return self.state()
    def _record(self, row: dict[str, Any], action: str | None, increment: int = 1) -> None:
        if action: self.last_actions["PLAYER_0"] = action
        self._write(row); self.history.append(row); self.decision_index += increment
    def _write(self, row: dict[str, Any]) -> None:
        with (self.telemetry_dir / f"{self.run_id}.jsonl").open("a", encoding="utf-8") as fh: fh.write(json.dumps(row, sort_keys=True) + "\n")
    def state(self) -> dict[str, Any]:
        with self.lock: return {"mode": self.mode, "status": self.status, "seed": self.seed, "run_id": self.run_id, "generation_id": self.generation_id, "episode_id": self.episode_id, "frame_index": self.frame_index, "decision_index": self.decision_index, "joint_step": self.joint_step, "score": self.score, "rewards": self.rewards, "lives": int(self.info.get("lives", 0)) if self.mode == "1P" else None, "last_actions": self.last_actions, "history": self.history[-30:], "players": {k: v.public() for k, v in self.seats.items()}, "frame_hash": digest(self.current_frame), "frame_url": "/frame.png", "telemetry_dir": str(self.telemetry_dir)}
    def integrations(self) -> dict[str, Any]:
        historical = {"TENKI": "prior sandbox receipt present", "MITOSIS_LABS": "prior memory/directive receipts present"}; return {r.provider_id: {**r.public(), "historical_evidence": historical.get(r.provider_id, "none recorded"), "current_status": r.live_probe} for r in self.registry.records()}


class Handler(BaseHTTPRequestHandler):
    controller: DemoController; server_version = "VithiaLiveDemo/2.0"
    def log_message(self, fmt: str, *args: Any) -> None: return
    def _send(self, status: int, body: bytes, content_type: str = "application/json") -> None: self.send_response(status); self.send_header("Content-Type", content_type); self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
    def _json(self, obj: Any, status: int = 200) -> None: self._send(status, json.dumps(obj, sort_keys=True).encode())
    def do_GET(self) -> None:
        path = urlparse(self.path).path
        try:
            if path == "/": self._send(200, (STATIC / "index.html").read_bytes(), "text/html; charset=utf-8")
            elif path in {"/app.js", "/styles.css"}: self._send(200, (STATIC / path[1:]).read_bytes(), "text/javascript; charset=utf-8" if path.endswith("js") else "text/css; charset=utf-8")
            elif path == "/frame.png": self._send(200, png_bytes(self.controller.current_frame), "image/png")
            elif path == "/api/state": self._json(self.controller.state())
            elif path == "/api/models": self._json({"models": self.controller.registry.models})
            elif path == "/api/integrations": self._json(self.controller.integrations())
            elif path == "/api/registry": self._json({"providers": [r.public() for r in self.controller.registry.records()]})
            else: self._json({"error": "not_found"}, 404)
        except Exception as exc: self._json({"error": type(exc).__name__, "detail": str(exc)}, 400)
    def do_POST(self) -> None:
        path = urlparse(self.path).path
        try:
            n = int(self.headers.get("Content-Length", "0")); payload = json.loads(self.rfile.read(n) or b"{}")
            if path == "/api/play": out = self.controller.play()
            elif path == "/api/pause": out = self.controller.pause()
            elif path == "/api/stop": out = self.controller.stop()
            elif path == "/api/step": out = self.controller.step_once()
            elif path == "/api/reset": out = self.controller.reset(payload.get("seed", self.controller.seed))
            elif path == "/api/mode": out = self.controller.set_mode(payload.get("mode"))
            elif path == "/api/config": out = self.controller.configure(payload)
            elif path.startswith("/api/seat/"): out = self.controller.set_seat(path.rsplit("/", 1)[-1], payload)
            else: self._json({"error": "not_found"}, 404); return
            self._json(out)
        except Exception as exc: self._json({"error": type(exc).__name__, "detail": str(exc)}, 400)


def serve(host: str = "127.0.0.1", port: int = 8788, telemetry_dir: str | None = None) -> ThreadingHTTPServer:
    Handler.controller = DemoController(telemetry_dir); server = ThreadingHTTPServer((host, port), Handler); server.controller = Handler.controller  # type: ignore[attr-defined]
    return server


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(); parser.add_argument("--host", default="127.0.0.1"); parser.add_argument("--port", type=int, default=8788); parser.add_argument("--telemetry-dir"); args = parser.parse_args(); httpd = serve(args.host, args.port, args.telemetry_dir); print(f"LIVE_DEMO_URL=http://{args.host}:{args.port}", flush=True)
    try: httpd.serve_forever()
    except KeyboardInterrupt: pass
    finally: httpd.controller._close_envs(); httpd.server_close()
