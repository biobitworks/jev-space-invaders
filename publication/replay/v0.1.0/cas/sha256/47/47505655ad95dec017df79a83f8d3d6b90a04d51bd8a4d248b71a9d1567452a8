#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
from zenodo_common import api_request, get_token

ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("role",choices=["preprint","fcg_dataset"])
    ap.add_argument("--publish",action="store_true")
    args=ap.parse_args()
    if not args.publish:
        print("ZENODO_PUBLISHED=NO")
        print("Refusing irreversible publication without --publish")
        return
    receipt=json.loads((ROOT/"receipts"/f"{args.role}_draft.json").read_text())
    dep=receipt["deposition"]
    print(f"ABOUT_TO_PUBLISH_ROLE={args.role}")
    print(f"DEPOSITION_ID={dep.get('id')}")
    print(f"TITLE={dep.get('title')}")
    print(f"RESERVED_DOI={((dep.get('metadata') or {}).get('prereserve_doi') or {}).get('doi','NOT_RESERVED')}")
    token=get_token()
    status,body=api_request("POST",dep["links"]["publish"],token=token)
    print(f"ZENODO_PUBLISH_HTTP_STATUS={status}")
    print(f"ZENODO_PUBLISHED={'YES' if status==202 else 'NO'}")
    if body:
        print(f"ZENODO_DOI={body.get('doi','UNKNOWN')}")
if __name__=="__main__": main()
