import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from src.deciders import ScriptedDecider, SystemOneHTTPDecider
from src.harness import record_run, run_episode
from src.validate import check

ROOT = Path(__file__).resolve().parents[1]


def test_scripted_episode_and_record(tmp_path):
    res = tmp_path / "results.json"
    res.write_text((ROOT / "results.json").read_text())
    before = check(json.loads(res.read_text()))["non_jev_runs"]
    dec = ScriptedDecider()
    run, trace = run_episode(dec, seed=1, max_steps=60, log_every=0)
    assert run["steps"] == 60 and run["model_calls"] == 0 and run["truncated"]
    assert run["frames"] >= run["steps"]
    out = record_run(run, trace, dec, res, push=False, note="test")
    d = json.loads(res.read_text())
    assert check(d)["non_jev_runs"] == before + 1
    assert (tmp_path / out["trace_file"]).exists()


def test_perception_sees_ship():
    dec = ScriptedDecider()
    _, trace = run_episode(dec, seed=2, max_steps=10, log_every=0)
    assert any(t["ship_x"] is not None for t in trace)


class _Fake(BaseHTTPRequestHandler):
    calls = 0

    def do_POST(self):
        _Fake.calls += 1
        self.rfile.read(int(self.headers["Content-Length"]))
        if _Fake.calls == 1:
            self.send_response(429); self.end_headers(); return
        body = json.dumps({"model": "fake-1", "answers": {"move": {"type": "choice", "choice": "LEFTFIRE",
                           "probabilities": {"LEFTFIRE": 0.7, "FIRE": 0.3}, "confidence": 0.55}},
                           "usage": {"input_tokens": 100, "output_tokens": 2}}).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def test_systemone_retry_and_fields():
    srv = HTTPServer(("127.0.0.1", 0), _Fake)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    dec = SystemOneHTTPDecider("openjev", f"http://127.0.0.1:{srv.server_port}")
    d = dec.decide({"step": 0}, "NOOP")
    srv.shutdown()
    assert d.action == "LEFTFIRE" and d.retries == 1 and d.errors == {"429": 1}
    assert d.served_model == "fake-1" and d.input_tokens == 100 and d.confidence == 0.55
