import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from src.openjev_client import OpenJevDecider


def test_openjev_client_exact_bytes_and_token(monkeypatch):
    monkeypatch.setenv("OPENJEV_TOKEN", "t0k")
    seen = {}

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            seen["auth"] = self.headers.get("Authorization")
            seen["body"] = self.rfile.read(int(self.headers["Content-Length"]))
            body = json.dumps({"model": "openjev-x", "answers": {"move": {"choice": "FIRE", "probabilities": {"FIRE": 1.0}}}}).encode()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    dec = OpenJevDecider(f"http://127.0.0.1:{srv.server_port}")
    body = dec.request_body({"state": {"x": 1}})
    d = dec.decide_body(body, "NOOP")
    srv.shutdown()
    assert seen["auth"] == "Bearer t0k" and seen["body"] == body
    assert d.action == "FIRE" and d.served_model == "openjev-x" and d.probabilities == {"FIRE": 1.0}
