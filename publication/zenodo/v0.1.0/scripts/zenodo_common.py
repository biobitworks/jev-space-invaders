#!/usr/bin/env python3
"""Shared Zenodo helper. Never prints or persists ZENODO_TOKEN."""
from __future__ import annotations
import json, os, urllib.error, urllib.parse, urllib.request
from pathlib import Path

def get_token() -> str:
    token=os.environ.get("ZENODO_TOKEN","").strip()
    if not token:
        raise SystemExit("ZENODO_TOKEN is not set")
    return token

def api_request(method: str, url: str, *, token: str, json_body=None, raw_body=None, content_type=None):
    headers={"Authorization":f"Bearer {token}"}
    data=None
    if json_body is not None:
        data=json.dumps(json_body).encode("utf-8")
        headers["Content-Type"]="application/json"
    elif raw_body is not None:
        data=raw_body
        if content_type:
            headers["Content-Type"]=content_type
    req=urllib.request.Request(url,data=data,headers=headers,method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            body=resp.read()
            return resp.status, (json.loads(body) if body else None)
    except urllib.error.HTTPError as e:
        body=e.read().decode("utf-8","replace")
        raise SystemExit(f"Zenodo HTTP {e.code}: {body}") from e

def load_ready_metadata(path: Path):
    wrapper=json.loads(path.read_text(encoding="utf-8"))
    metadata=wrapper.get("metadata",wrapper)
    missing=[k for k in ("upload_type","title","creators","description","access_right","publication_date") if not metadata.get(k)]
    if metadata.get("access_right") in ("open","embargoed") and not metadata.get("license"):
        missing.append("license")
    if metadata.get("upload_type")=="publication" and not metadata.get("publication_type"):
        missing.append("publication_type")
    if missing:
        raise SystemExit("Metadata is not publication-ready; missing: "+", ".join(sorted(set(missing))))
    return metadata

def dump_receipt(path: Path, obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,sort_keys=True)+"\n",encoding="utf-8")
