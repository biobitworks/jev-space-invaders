import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import verify_doctor3_ollama_local as V
import vithia_fcg as F

def M(name, size, **kw): return {"name": name, "size": size, **kw}

def test_cloud_models_are_detected():
    assert V.is_cloud(M("x:cloud", 1)) and V.is_cloud(M("y-cloud", 1)) and V.is_cloud(M("z", 1, remote_host="h"))
    assert not V.is_cloud(M("llama3.2:3b", 1))

def test_prefers_llama32_3b_and_never_cloud_or_embedding():
    tags = [M("qwen2.5:0.5b", 5), M("llama3.2:3b", 20), M("big:cloud", 1), M("nomic-embed-text:latest", 2), M("deepseek-r1:14b", 90)]
    got = V.choose_models(tags, None)
    assert got[0] == "llama3.2:3b" and "big:cloud" not in got and "nomic-embed-text:latest" not in got and "deepseek-r1:14b" not in got
    assert got[1:] == ["qwen2.5:0.5b"]

def test_falls_back_to_smallest_local_when_preferred_absent():
    assert V.choose_models([M("b", 30), M("a", 10), M("c:cloud", 1)], None)[0] == "a"

def test_forced_model_must_be_installed_and_local():
    assert V.choose_models([M("a", 1)], "a") == ["a"] and V.choose_models([M("a", 1)], "nope") == [] and V.choose_models([M("a:cloud", 1)], "a:cloud") == []

def test_kv_parser_takes_last_match():
    assert V.kv("X=1\nY=2\nX=3\n", "X") == "3" and V.kv("nothing", "X") is None

def test_adapter_wiring_check_passes_on_real_engine():
    w = V.wiring_check(F)
    assert w["state"] == "PASS", w

def test_supported_tier_ordering():
    assert V.TIER["WITHHOLD_ALL_TENKI_CLAIMS"] < V.TIER["PUBLISH_CLAIM_ARTIFACT_VERIFIED_ONLY"] < V.TIER["PUBLISH_CLAIM_REPLAY_COMPLETE"]


def test_host_name_falls_back_when_scutil_is_absent(monkeypatch):
    import shutil, socket
    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert V.host_name() == socket.gethostname()
