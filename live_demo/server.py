#!/usr/bin/env python3
"""Local-only live Vithia-Space gameplay UI.

This module is deliberately noncanonical until an operator admits a run. It
reuses the governed ALE perception/action substrate, supports a public
Vita01/A5 context preprocessor, dynamically discovers local Ollama models, and
can expose 1P plus ROM-gated PettingZoo 2P. It never rewrites competition
results or breakpoints.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import numpy as np

from experiments.e4a_snapshots import anticube
from experiments.e4b_ablation import path_distribution
from experiments.e5_2p import ONTOLOGY_PZ, rom_gate, seat_context, seat_state
from src.actions import ACTIONS, ACTION_TO_ID
from src.deciders import MOVE_QUESTION, ScriptedDecider
from src.envcfg import make_env
from src.perception import Perception
from src.s01.canon import content_id

ROOT = Path(__file__).resolve().parents[1]
STATIC = Path(__file__).resolve().parent / "index.html"
LOG_ROOT = Path(os.environ.get("VITHIA_LIVE_LOG_DIR", "/tmp/vithia-space-live-demo"))
OLLAMA_BASE = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
OPENJEV_TARGETED_BASE = os.environ.get("OPENJEV_TARGETED_BASE_URL", "").rstrip("/")
VALID_1P = tuple(ACTIONS)
VALID_2P = tuple(ONTOLOGY_PZ)
TOKEN_RE = re.compile(r"LEFTFIRE|RIGHTFIRE|NOOP|FIRE|RIGHT|LEFT|UP|DOWN", re.I)


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def jread(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def integrations() -> dict:
    mitosis = jread(ROOT / "evidence/competition/final_execution/MITOSIS_FINAL_EXECUTION_RECEIPT.json")
    tenki = jread(ROOT / "evidence/competition/final_execution/TENKI_FINAL_EXECUTION_RECEIPT.json")
    tenki_prior = jread(ROOT / "evidence/competition/tenki/TENKI_MITOSIS_RUNTIME_RECEIPT.json")
    oj = jread(ROOT / "evidence/openjev/RUNTIME_MANIFEST.json")
    liquid = jread(ROOT / "evidence/liquid/RUNTIME_MANIFEST.json")
    return {
        "mitosis": {
            "state": mitosis.get("state", "UNKNOWN"),
            "used": mitosis.get("MITOSIS_USED"),
            "universal_id": mitosis.get("remember_universal_id"),
            "retrieval_ms": mitosis.get("retrieval_took_ms"),
            "scope": "receipt-backed; no live Cortex mutation from this UI",
        },
        "tenki": {
            "final_state": tenki.get("state", "UNKNOWN"),
            "final_used": tenki.get("TENKI_USED"),
            "prior_runtime_state": "EXECUTED" if tenki_prior.get("execution") else "UNKNOWN",
            "prior_session_id": tenki_prior.get("session_id"),
            "scope": "prior sandbox evidence retained; final re-access may be blocked",
        },
        "openjev": {
            "matched_state": "NOT_TESTED_CAPABILITY_MISMATCH",
            "runtime_loaded": oj.get("OPENJEV_LOADED", "NO"),
            "targeted_demo_endpoint_configured": bool(OPENJEV_TARGETED_BASE),
            "scope": "targeted demo is exploratory, NON_TYPESAFE_JEV, NON_COUNTED, NONCOMPARABLE",
        },
        "liquid_ai": {
            "runtime_state": liquid.get("state", liquid.get("LIQUID_LOADED", "UNKNOWN")),
            "scope": "local Ollama-discovered Liquid-family models are selectable by exact served name",
        },
        "vithia_space_preprocessor": {
            "state": "AVAILABLE",
            "arm": "A5_VITA01_FULL",
            "components": ["history", "anticube", "public_path_distribution"],
            "private_s0": "NOT_USED",
        },
    }


def ollama_models() -> list[str]:
    try:
        with urllib.request.urlopen(OLLAMA_BASE + "/api/tags", timeout=3) as r:
            d = json.loads(r.read())
        return [m["name"] for m in d.get("models", []) if m.get("name")]
    except Exception:
        return []


def normalize_action(text: str, legal: tuple[str, ...]) -> list[str]:
    upper = (text or "").upper()
    tokens = [m.group(0).upper() for m in TOKEN_RE.finditer(upper)]
    out = []
    for tok in tokens:
        if tok in legal and tok not in out:
            out.append(tok)
        elif tok in legal:
            out.append(tok)
    if out:
        return out
    low = (text or "").strip().lower()
    aliases = {
        "wait": "NOOP", "noop": "NOOP", "fire": "FIRE",
        "move left": "LEFT", "move right": "RIGHT",
        "fire left": "LEFTFIRE", "left fire": "LEFTFIRE",
        "fire right": "RIGHTFIRE", "right fire": "RIGHTFIRE",
        "up": "UP", "down": "DOWN",
    }
    a = aliases.get(low)
    return [a] if a in legal else []


def compile_vithia_1p(state: dict, history: list[dict], depth: int) -> dict:
    h = []
    for i, x in enumerate(history[-depth:]):
        s = x["state"]
        h.append({
            "steps_ago": len(history[-depth:]) - i,
            "ship_x": (s.get("ship") or {}).get("x"),
            "bombs": [[b.get("x"), b.get("y_bottom")] for b in s.get("bombs", [])],
            "action": x.get("action"),
        })
    return {
        "state": state,
        "history": h,
        "anticube": anticube(state),
        "path_distribution": path_distribution(state),
        "preprocessor": "A5_VITA01_FULL_PUBLIC",
    }


class Controller:
    def __init__(self, name: str):
        self.name = name

    def decide(self, context: dict, legal: tuple[str, ...], forecast: int, prev: str) -> dict:
        raise NotImplementedError


class ScriptedController(Controller):
    def __init__(self):
        super().__init__("SCRIPTED_BASELINE")
        self.dec = ScriptedDecider()

    def decide(self, context, legal, forecast, prev):
        state = context.get("state", context)
        d = self.dec.decide(state, prev)
        plan = [d.action] * forecast
        return {
            "action": d.action, "plan": plan, "confidence": None,
            "reason": "non-model reference sweep", "latency_ms": 0.0,
            "served_model": "scripted-policy", "fallback": False,
            "raw": d.action,
        }


class OllamaController(Controller):
    def __init__(self, model: str):
        super().__init__(model)

    def decide(self, context, legal, forecast, prev):
        legal_text = " ".join(legal)
        prompt = (
            "Atari Space Invaders controller. Valid actions ONLY: " + legal_text + ".\n"
            f"Return {1 + forecast} action tokens separated by spaces. Token 1 executes NOW; "
            f"the next {forecast} tokens are projections and will be replanned. "
            "Use only valid action tokens. No explanation.\nSTATE="
            + json.dumps(context, sort_keys=True, separators=(",", ":"))
        )
        body = json.dumps({
            "model": self.name,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0, "num_predict": max(12, (forecast + 1) * 4)},
        }).encode()
        req = urllib.request.Request(
            OLLAMA_BASE + "/api/generate", data=body,
            headers={"Content-Type": "application/json"}, method="POST"
        )
        t0 = time.perf_counter()
        raw = ""
        error = None
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                resp = json.loads(r.read())
            raw = resp.get("response") or ""
            served = resp.get("model") or self.name
        except Exception as e:
            error = type(e).__name__
            served = self.name
        ms = (time.perf_counter() - t0) * 1000
        toks = normalize_action(raw, legal)
        ok = bool(toks)
        action = toks[0] if ok else (prev if prev in legal else legal[0])
        plan = toks[1:1 + forecast]
        plan += ["UNKNOWN"] * max(0, forecast - len(plan))
        return {
            "action": action, "plan": plan, "confidence": None,
            "reason": "projected by local model" if ok else f"fallback:{error or 'invalid_model_output'}",
            "latency_ms": round(ms, 2), "served_model": served,
            "fallback": not ok, "raw": raw[:240],
        }


class OpenJevTargetedController(Controller):
    def __init__(self):
        super().__init__("OPENJEV_TARGETED_EXPLORATORY")

    def decide(self, context, legal, forecast, prev):
        if not OPENJEV_TARGETED_BASE:
            return {
                "action": prev, "plan": ["UNKNOWN"] * forecast, "confidence": None,
                "reason": "CAPABILITY_GATED: OPENJEV_TARGETED_BASE_URL not set",
                "latency_ms": 0.0, "served_model": "openjev",
                "fallback": True, "raw": "",
            }
        criteria = {a: a for a in legal}
        body = json.dumps({
            "state": context, "model": "openjev",
            "questions": {"move": {"type": "choice", "instructions": "Choose one legal action.", "criteria": criteria}}
        }).encode()
        req = urllib.request.Request(
            OPENJEV_TARGETED_BASE + "/v1/systemone", data=body,
            headers={"Content-Type": "application/json"}, method="POST"
        )
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                resp = json.loads(r.read())
            ans = resp.get("answers", {}).get("move", {})
            choice = ans.get("choice")
            ok = choice in legal
            return {
                "action": choice if ok else prev,
                "plan": ["UNKNOWN"] * forecast,
                "confidence": ans.get("confidence"),
                "reason": "OpenJEV targeted exploratory current-action readout",
                "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
                "served_model": resp.get("model") or "openjev",
                "fallback": not ok, "raw": json.dumps(ans)[:240],
            }
        except Exception as e:
            return {
                "action": prev, "plan": ["UNKNOWN"] * forecast, "confidence": None,
                "reason": f"OpenJEV request failed:{type(e).__name__}",
                "latency_ms": round((time.perf_counter() - t0) * 1000, 2),
                "served_model": "openjev", "fallback": True, "raw": "",
            }


def controller(name: str) -> Controller:
    if name == "SCRIPTED_BASELINE":
        return ScriptedController()
    if name == "OPENJEV_TARGETED_EXPLORATORY":
        return OpenJevTargetedController()
    return OllamaController(name)


class OnePlayer:
    mode = "1P"

    def __init__(self, model: str, seed: int, preprocessor: bool, backtrace: int, forecast: int):
        self.model_name = model
        self.seed = seed
        self.preprocessor = preprocessor
        self.backtrace = backtrace
        self.forecast = forecast
        self.history: list[dict] = []
        self.reset()

    def reset(self):
        if getattr(self, "env", None):
            self.env.close()
        self.env = make_env()
        self.perception = Perception()
        self.obs, self.info = self.env.reset(seed=self.seed)
        self.score = 0.0
        self.prev = "NOOP"
        self.step_n = 0
        self.done = False
        self.last_state = None
        self.last_projection = []
        self.last_latency = None
        self.history.clear()

    def step(self):
        if self.done:
            return
        state = self.perception.observe(
            self.obs, lives=int(self.info.get("lives", 0)), score=self.score,
            step=self.step_n, prev_action=self.prev
        )
        ctx = compile_vithia_1p(state, self.history, self.backtrace) if self.preprocessor else {"state": state}
        d = controller(self.model_name).decide(ctx, VALID_1P, self.forecast, self.prev)
        before = self.score
        obs, reward, term, trunc, info = self.env.step(ACTION_TO_ID[d["action"]])
        self.score += float(reward)
        rec = {
            "utc": now(), "decision": self.step_n, "state_id": content_id(state),
            "action": d["action"], "projected": d["plan"], "model": d["served_model"],
            "latency_ms": d["latency_ms"], "reward": float(reward),
            "score_before": before, "score_after": self.score,
            "lives": int(info.get("lives", 0)), "confidence": d["confidence"],
            "fallback": d["fallback"], "reason": d["reason"], "state": state,
        }
        self.history.append(rec)
        self.obs, self.info = obs, info
        self.prev = d["action"]
        self.last_state = state
        self.last_projection = d["plan"]
        self.last_latency = d["latency_ms"]
        self.step_n += 1
        self.done = bool(term or trunc)


class TwoPlayer:
    mode = "2P"

    def __init__(self, model_a: str, model_b: str, seed: int, preprocessor: bool, backtrace: int, forecast: int):
        self.model_a, self.model_b = model_a, model_b
        self.model_name = model_a
        self.seed = seed
        self.preprocessor = preprocessor
        self.backtrace = backtrace
        self.forecast = forecast
        self.history: list[dict] = []
        self.blocked = None
        self.reset()

    def reset(self):
        gate = rom_gate(os.environ.get("VITHIA_2P_ROM_DIR"))
        if gate.get("state") != "ROM_PRESENT":
            self.blocked = gate
            self.done = True
            self.obs = None
            self.score = {}
            self.step_n = 0
            return
        try:
            from pettingzoo.atari import space_invaders_v2
            self.env = space_invaders_v2.parallel_env()
            self.obs, self.infos = self.env.reset(seed=self.seed)
        except Exception as e:
            self.blocked = {"state": "2P_RUNTIME_BLOCKED", "reason": repr(e)}
            self.done = True
            self.obs = None
            self.score = {}
            self.step_n = 0
            return
        self.blocked = None
        self.percs = {s: Perception() for s in self.env.agents}
        self.score = {s: 0.0 for s in self.env.agents}
        self.states_hist = {s: [] for s in self.env.agents}
        self.prev = {s: "NOOP" for s in self.env.agents}
        self.step_n = 0
        self.done = False
        self.history.clear()
        self.last_projection = {}
        self.last_latency = {}

    def step(self):
        if self.done or self.blocked:
            return
        agents = list(self.env.agents)
        if len(agents) < 2:
            self.done = True
            return
        colours = {"first_0": (50, 132, 50), "second_0": (162, 134, 56)}
        models = {agents[0]: self.model_a, agents[1]: self.model_b}
        acts, meta = {}, {}
        for seat in agents:
            frame = self.obs[seat]
            base = self.percs[seat].observe(
                frame, lives=0, score=self.score.get(seat, 0.0),
                step=self.step_n, prev_action=self.prev.get(seat, "NOOP")
            )
            st = seat_state(base, frame, seat, colours)
            ctx = seat_context("VITA01" if self.preprocessor else "OJ", st, self.states_hist[seat][-self.backtrace:])
            d = controller(models[seat]).decide(ctx, VALID_2P, self.forecast, self.prev.get(seat, "NOOP"))
            a = d["action"] if d["action"] in VALID_2P else "NOOP"
            acts[seat] = VALID_2P.index(a)
            meta[seat] = {**d, "action": a, "state_id": content_id(st), "state": st}
            self.states_hist[seat].append(st)
            self.prev[seat] = a
        obs, rew, terms, truncs, infos = self.env.step(acts)
        for seat, reward in rew.items():
            self.score[seat] = self.score.get(seat, 0.0) + float(reward)
        rec = {
            "utc": now(), "decision": self.step_n,
            "seats": {
                seat: {
                    "action": meta[seat]["action"], "projected": meta[seat]["plan"],
                    "model": meta[seat]["served_model"], "latency_ms": meta[seat]["latency_ms"],
                    "reward": float(rew.get(seat, 0.0)), "score_after": self.score.get(seat, 0.0),
                    "fallback": meta[seat]["fallback"], "reason": meta[seat]["reason"],
                } for seat in meta
            }
        }
        self.history.append(rec)
        self.obs, self.infos = obs, infos
        self.step_n += 1
        self.done = not self.env.agents or all(terms.get(s, False) or truncs.get(s, False) for s in terms)


class LiveApp:
    def __init__(self):
        LOG_ROOT.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        models = ollama_models()
        default = models[0] if models else "SCRIPTED_BASELINE"
        self.cfg = {
            "mode": "1P", "model_a": default, "model_b": default, "seed": 3,
            "preprocessor": True, "backtrace": 6, "forecast": 6, "speed": "MODEL_PACED",
        }
        self.session: OnePlayer | TwoPlayer = OnePlayer(default, 3, True, 6, 6)
        self.playing = False
        self.paused = True
        self.stopped = False
        self.thread = None
        self.log_path = LOG_ROOT / f"live_{int(time.time())}.jsonl"

    def available_models(self):
        ms = ollama_models()
        out = [{"name": m, "kind": "OLLAMA", "enabled": True} for m in ms]
        out.append({"name": "SCRIPTED_BASELINE", "kind": "NON_MODEL_REFERENCE", "enabled": True})
        out.append({
            "name": "OPENJEV_TARGETED_EXPLORATORY", "kind": "OPEN_SOURCE_JEV_STANDIN",
            "enabled": bool(OPENJEV_TARGETED_BASE),
            "note": "NON_TYPESAFE_JEV / NON_COUNTED / NONCOMPARABLE",
        })
        return out

    def _new_session(self):
        c = self.cfg
        if c["mode"] == "2P":
            self.session = TwoPlayer(c["model_a"], c["model_b"], c["seed"], c["preprocessor"], c["backtrace"], c["forecast"])
        else:
            self.session = OnePlayer(c["model_a"], c["seed"], c["preprocessor"], c["backtrace"], c["forecast"])

    def configure(self, body: dict):
        with self.lock:
            was = self.playing and not self.paused
            self.paused = True
            for k in ("mode", "model_a", "model_b", "seed", "preprocessor", "backtrace", "forecast", "speed"):
                if k in body:
                    self.cfg[k] = body[k]
            self.cfg["backtrace"] = max(1, min(12, int(self.cfg["backtrace"])))
            self.cfg["forecast"] = max(1, min(12, int(self.cfg["forecast"])))
            self.cfg["seed"] = int(self.cfg["seed"])
            self._new_session()
            self.playing = False
            self.stopped = False
            return {"ok": True, "was_playing": was}

    def reset(self):
        with self.lock:
            self.paused = True
            self.playing = False
            self.stopped = False
            self._new_session()

    def play(self):
        with self.lock:
            self.playing, self.paused, self.stopped = True, False, False
            if not self.thread or not self.thread.is_alive():
                self.thread = threading.Thread(target=self._loop, daemon=True)
                self.thread.start()

    def pause(self):
        with self.lock:
            self.paused = True

    def stop(self):
        with self.lock:
            self.playing, self.paused, self.stopped = False, True, True

    def step_once(self):
        with self.lock:
            self.paused = True
            self.playing = False
            self._step_locked()

    def _log_latest(self):
        if not self.session.history:
            return
        rec = {"mode": self.session.mode, "config": dict(self.cfg), **self.session.history[-1]}
        with self.log_path.open("a") as f:
            f.write(json.dumps(rec, separators=(",", ":")) + "\n")

    def _step_locked(self):
        if getattr(self.session, "done", False):
            return
        self.session.step()
        self._log_latest()

    def _loop(self):
        while True:
            with self.lock:
                if self.stopped:
                    return
                if self.playing and not self.paused:
                    t0 = time.perf_counter()
                    self._step_locked()
                    if getattr(self.session, "done", False):
                        self.playing, self.paused = False, True
                    elapsed = time.perf_counter() - t0
                    speed = self.cfg["speed"]
                else:
                    elapsed, speed = 0, "PAUSED"
            if speed == "1X_VISUAL":
                time.sleep(max(0.0, 0.20 - elapsed))
            elif speed == "FAST":
                time.sleep(0.001)
            else:
                time.sleep(0.03)

    def snapshot(self) -> dict:
        with self.lock:
            s = self.session
            frame = None
            if s.mode == "1P" and getattr(s, "obs", None) is not None:
                frame = s.obs
            elif s.mode == "2P" and getattr(s, "obs", None):
                seat = next(iter(s.obs), None)
                frame = s.obs.get(seat) if seat else None
            fr = None
            if isinstance(frame, np.ndarray) and frame.ndim == 3:
                a = np.ascontiguousarray(frame.astype(np.uint8))
                fr = {
                    "width": int(a.shape[1]), "height": int(a.shape[0]),
                    "rgb_b64": base64.b64encode(a.tobytes()).decode(),
                    "sha256": hashlib.sha256(a.tobytes()).hexdigest(),
                }
            hist = s.history[-40:]
            if s.mode == "1P":
                score = s.score
                lives = int(getattr(s, "info", {}).get("lives", 0))
                projection = getattr(s, "last_projection", [])
            else:
                score = getattr(s, "score", {})
                lives = None
                projection = hist[-1].get("seats", {}) if hist else {}
            return {
                "mode": s.mode, "config": dict(self.cfg), "playing": self.playing,
                "paused": self.paused, "stopped": self.stopped,
                "done": getattr(s, "done", False), "blocked": getattr(s, "blocked", None),
                "step": getattr(s, "step_n", 0), "score": score, "lives": lives,
                "frame": fr, "history": hist, "projection": projection,
                "log_path": str(self.log_path),
                "success": {
                    "baseline_exceeded": isinstance(score, (int, float)) and score > 270,
                    "scripted_reference_exceeded": isinstance(score, (int, float)) and score > 325,
                },
            }


APP = LiveApp()


class Handler(BaseHTTPRequestHandler):
    server_version = "VithiaLive/0.1"

    def log_message(self, fmt, *args):
        return

    def _send(self, code: int, body: bytes, ctype="application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj).encode())

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}")

    def do_GET(self):
        if self.path == "/":
            self._send(200, STATIC.read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/state":
            self._json(APP.snapshot())
        elif self.path == "/api/models":
            self._json({"models": APP.available_models()})
        elif self.path == "/api/integrations":
            self._json(integrations())
        else:
            self._json({"error": "not_found"}, 404)

    def do_POST(self):
        try:
            body = self._body()
            if self.path == "/api/config":
                self._json(APP.configure(body))
            elif self.path == "/api/play":
                APP.play(); self._json({"ok": True})
            elif self.path == "/api/pause":
                APP.pause(); self._json({"ok": True})
            elif self.path == "/api/stop":
                APP.stop(); self._json({"ok": True})
            elif self.path == "/api/reset":
                APP.reset(); self._json({"ok": True})
            elif self.path == "/api/step":
                APP.step_once(); self._json({"ok": True})
            else:
                self._json({"error": "not_found"}, 404)
        except Exception as e:
            self._json({"error": type(e).__name__, "detail": str(e)}, 500)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8788)
    args = ap.parse_args()
    if args.host not in ("127.0.0.1", "localhost"):
        raise SystemExit("live demo must bind loopback only")
    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"LIVE_URL=http://{args.host}:{args.port}")
    print(f"LOG_PATH={APP.log_path}")
    print("CANONICAL_REPO_MUTATED=NO")
    srv.serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
