import json
from unittest.mock import patch
from experiments import e5_2p
from src.openjev_client_pz import PZOpenJevDecider,PZ_ACTIONS

class Resp:
    def __enter__(self): return self
    def __exit__(self,*a): return False
    def read(self):
        return json.dumps({"model":"fake","answers":{"move":{"choice":"UP","probabilities":{"UP":0.8},"confidence":0.8}}}).encode()

def test_pz_client_accepts_up_without_fallback(monkeypatch):
    monkeypatch.setenv("OPENJEV_TOKEN","test-only")
    d=PZOpenJevDecider("http://127.0.0.1:9","openjev",max_retries=0,timeout_s=1)
    with patch("urllib.request.urlopen",return_value=Resp()):
        out=d.decide_body(b"{}", "NOOP")
    assert out.action=="UP"
    assert out.proposed_action=="UP"
    assert not out.fallback

def test_pz_client_ontology_exactly_matches_e5_2p():
    assert tuple(PZ_ACTIONS)==tuple(e5_2p.ONTOLOGY_PZ)
    assert PZ_ACTIONS[2]=="UP"

