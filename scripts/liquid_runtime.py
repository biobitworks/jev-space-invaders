#!/usr/bin/env python3
"""Verify the exact LiquidAI GGUF + external Ollama runtime. Never downloads or mutates the model."""
from __future__ import annotations
import hashlib,json,platform,subprocess,sys,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from src.liquid_client import LiquidOllamaDecider
MODEL_FILE=Path("/Volumes/magicBLACKbox/liquid/LFM2.5-1.2B-Instruct-GGUF/LFM2.5-1.2B-Instruct-Q4_0.gguf")
EXPECTED_SHA="2ea801949d760cdf1a2cc04a54262c22c3c0c54f0769d57760c9adeb0e59233f"
SOURCE_REPO="LiquidAI/LFM2.5-1.2B-Instruct-GGUF"
MODEL_TAG="liquid-vithia-1.2b:latest"; ENDPOINT="http://127.0.0.1:11437"
OUT=ROOT/"evidence/liquid/RUNTIME_MANIFEST.json"
def sh(cmd):
    return subprocess.run(cmd,capture_output=True,text=True).stdout.strip()
def verify():
    if not MODEL_FILE.exists(): raise SystemExit("Liquid GGUF missing")
    sha=hashlib.sha256(MODEL_FILE.read_bytes()).hexdigest()
    if sha!=EXPECTED_SHA: raise SystemExit(f"Liquid weight hash mismatch {sha}")
    with urllib.request.urlopen(ENDPOINT+"/api/tags",timeout=5) as r: tags=json.load(r)
    names={m.get("name") for m in tags.get("models",[])}
    if MODEL_TAG not in names: raise SystemExit(f"{MODEL_TAG} not resident in external Ollama store")
    dec=LiquidOllamaDecider(ENDPOINT,MODEL_TAG,timeout_s=60,max_retries=0)
    body=dec.request_body({"state":{"label":"SETUP_SMOKE","note":"NON_EXPERIMENTAL"}})
    d=dec.decide_body(body,"NOOP")
    if d.fallback or d.proposed_action not in ("NOOP","FIRE","RIGHT","LEFT","RIGHTFIRE","LEFTFIRE"):
        raise SystemExit(f"Liquid setup smoke failed: {d}")
    try:
        import urllib.request as u
        info=json.load(u.urlopen("https://huggingface.co/api/models/"+SOURCE_REPO,timeout=10))
        revision=info.get("sha")
    except Exception:
        revision="NOT_COMPUTED_NETWORK_UNAVAILABLE"
    man={"schema":"LIQUID_RUNTIME_MANIFEST_V1","LIQUID_LOADED":"YES","provider":"liquid",
         "served_model":MODEL_TAG,"source_repo":SOURCE_REPO,"source_revision":revision,
         "weight_file":str(MODEL_FILE),"weight_bytes":MODEL_FILE.stat().st_size,"weight_sha256":sha,
         "quantization":"Q4_0 GGUF","endpoint":ENDPOINT,"engine":"Ollama","ollama_version":sh(["ollama","--version"]),
         "host":"magicSTUDIObox","platform":platform.platform(),"chip":sh(["sysctl","-n","machdep.cpu.brand_string"]),
         "ram_bytes":int(sh(["sysctl","-n","hw.memsize"])),"setup_smoke":"PASS",
         "probabilities":"NOT_AVAILABLE","confidence":"NOT_AVAILABLE",
         "labels":["NON_TYPESAFE_JEV","NON_OPENJEV","NON_COUNTED_FOR_TYPESAFE_PERFORMANCE"]}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(man,indent=2)+"\n")
    return man
if __name__=="__main__": print(json.dumps(verify(),indent=2))

