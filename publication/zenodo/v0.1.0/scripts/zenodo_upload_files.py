#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, mimetypes, urllib.parse
from pathlib import Path
from zenodo_common import api_request, get_token

ROOT=Path(__file__).resolve().parents[1]
def sha256(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):h.update(chunk)
    return h.hexdigest()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("role",choices=["preprint","fcg_dataset"])
    ap.add_argument("--execute",action="store_true")
    args=ap.parse_args()
    receipt=json.loads((ROOT/"receipts"/f"{args.role}_draft.json").read_text())
    dep=receipt["deposition"]
    bucket=dep["links"]["bucket"].rstrip("/")
    manifest=json.loads((ROOT/"ZENODO_FILE_MANIFEST.json").read_text())
    field="include_in_preprint_record" if args.role=="preprint" else "include_in_dataset_record"
    selected=[x for x in manifest["files"] if x.get(field)]
    if not selected: raise SystemExit("No files selected for role")
    token=get_token() if args.execute else None
    for item in selected:
        p=ROOT/item["package_relative_path"]
        if not p.exists(): raise SystemExit(f"Missing upload file: {p}")
        got=sha256(p)
        if got!=item["sha256"]: raise SystemExit(f"SHA256 mismatch before upload: {p}")
        url=bucket+"/"+urllib.parse.quote(item["filename"])
        print(f"UPLOAD {args.role}: {item['filename']} sha256={got} bytes={p.stat().st_size}")
        if not args.execute: continue
        ctype=item.get("media_type") or mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        status,body=api_request("PUT",url,token=token,raw_body=p.read_bytes(),content_type=ctype)
        print(f"UPLOADED status={status} server_checksum={(body or {}).get('checksum')}")
    print(f"ZENODO_FILES_UPLOADED={'YES' if args.execute else 'DRY_RUN'}")
if __name__=="__main__": main()
