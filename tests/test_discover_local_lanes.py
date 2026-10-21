import http.server, json, os, socketserver, sys, threading
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import discover_local_lanes as D


def M(name, size, runtime="ollama", local=True, embed=False):
    return {"runtime": runtime, "endpoint": "http://127.0.0.1:1", "name": name, "size": size, "local": local, "classification": "local" if local else "cloud/remote",
            "capabilities": None, "embedding_only": embed, "available": True, "family": D.family_of(name)}


def test_family_of_groups_by_family_not_by_variant():
    assert D.family_of("hf.co/LiquidAI/LFM2.5-1.2B-Instruct-GGUF:Q4_K_M") == "liquid" and D.family_of("qwen3:1.7b") == "qwen" == D.family_of("qwen2.5-coder:7b")
    assert D.family_of("llama3.2:3b") == "llama" and D.family_of("granite4.1:3b") == "granite" and D.family_of("phi4-reasoning:14b") == "phi"
    assert D.family_of("weirdmodel:7b") == "weirdmodel"

def test_usable_excludes_cloud_embedding_and_duplicates_but_never_by_family():
    pool = [M("x:cloud", 1, local=False), M("nomic-embed-text", 2, embed=True), M("deepseek-r1:14b", 9), M("qwen3:1.7b", 3), M("qwen3:1.7b", 3, runtime="ollarma")]
    names = [(m["runtime"], m["name"]) for m in D.usable(pool)]
    assert names == [("ollama", "deepseek-r1:14b"), ("ollama", "qwen3:1.7b")]           # reasoning models are NOT excluded; the Ollama copy wins the duplicate

def test_selection_prefers_liquid_then_qwen3_then_family_diversity():
    pool = [M("llama3.2:3b", 20), M("llama3.2:1b", 13), M("qwen2.5:0.5b", 4), M("qwen3:1.7b", 14), M("granite4.1:3b", 21), M("hf.co/LiquidAI/LFM2.5:Q4", 7), M("deepseek-r1:14b", 90)]
    got = [m["name"] for m in D.select_lanes(pool)]
    assert got[:2] == ["hf.co/LiquidAI/LFM2.5:Q4", "qwen3:1.7b"] and len(got) == 4
    assert {D.family_of(n) for n in got} == {"liquid", "qwen", "llama", "granite"}       # smallest of each remaining family, no duplicate variants

def test_selection_without_liquid_or_qwen3_uses_what_exists():
    got = [m["name"] for m in D.select_lanes([M("qwen2.5:1.5b", 5), M("qwen2.5:0.5b", 2), M("llama3.2:1b", 9)])]
    assert got == ["qwen2.5:0.5b", "llama3.2:1b", "qwen2.5:1.5b"]                        # qwen (smallest, no qwen3), then llama, then a 2nd variant only because slots remain

def test_only_two_usable_models_means_two_lanes_and_nothing_is_invented():
    got = D.select_lanes([M("a:1b", 1), M("b:1b", 2)])
    assert len(got) == 2 and D.select_lanes([]) == []
    assert D.lane_spec([], None) == "scripted"

def test_lane_spec_labels_runtime_and_adds_openjev_only_when_positively_identified():
    ch = [M("m1", 1), M("m2", 2, runtime="ollarma")]
    assert D.lane_spec(ch, {"status": "NOT_RUNNING"}) == "scripted,ollama:m1,ollarma:m2"
    assert D.lane_spec(ch, {"status": "RUNNING_IDENTIFIED_BY_REPO_HELPER"}).endswith(",openjev")

def _serve(routes):
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            r = routes.get(self.path)
            code, obj = r if r else (404, {})
            raw = json.dumps(obj).encode(); self.send_response(code); self.send_header("Content-Length", str(len(raw))); self.end_headers(); self.wfile.write(raw)
        def log_message(self, *a): pass
    srv = socketserver.TCPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start(); return srv, srv.server_address[1]

def test_ollarma_identified_only_by_bridge_status_and_kept_separate_from_ollama():
    srv, port = _serve({"/api/ollarma/bridge-status": (200, {"verdict": "PASS", "extra": 1}), "/api/tags": (200, {"models": [{"name": "routed:1b", "size": 5}]})})
    d = D.discover_ollarma({"WATCHTOWER_PORT": str(port)}); srv.shutdown()
    assert d["status"] == "RUNNING_IDENTIFIED_BY_BRIDGE_STATUS" and d["ollama_compatible_api"] == "YES" and [m["runtime"] for m in d["models"]] == ["ollarma"]

def test_ollarma_identified_but_not_ollama_compatible_contributes_no_models():
    srv, port = _serve({"/api/ollarma/bridge-status": (200, {"verdict": "PASS"})})
    d = D.discover_ollarma({"WATCHTOWER_PORT": str(port)}); srv.shutdown()
    assert d["status"].startswith("RUNNING_IDENTIFIED") and d["ollama_compatible_api"].startswith("NO") and d["models"] == []

def test_foreign_listener_is_never_treated_as_ollarma():
    srv, port = _serve({})                                   # something listens but is not Watchtower
    d = D.discover_ollarma({"WATCHTOWER_PORT": str(port)}); srv.shutdown()
    assert not d["status"].startswith("RUNNING_IDENTIFIED") and d["models"] == []

def test_ollarma_not_running_when_nothing_listens():
    assert D.discover_ollarma({"WATCHTOWER_PORT": "9"})["status"] == "NOT_RUNNING"

def test_openjev_not_running_without_state_and_never_guesses_a_port(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENJEV_HOME", str(tmp_path))
    d = D.discover_openjev(start=False)
    assert d["status"] == "NOT_RUNNING" and d["endpoint"] is None

def test_openjev_start_without_existing_weights_is_not_available_and_downloads_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENJEV_HOME", str(tmp_path))
    d = D.discover_openjev(start=True)
    assert d["status"] == "NOT_AVAILABLE_NO_EXISTING_RUNTIME" and not (tmp_path / "openjev-MLX-4bit").exists()
