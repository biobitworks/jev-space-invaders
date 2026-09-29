#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
from zenodo_common import api_request, get_token

ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--execute",action="store_true",help="perform authenticated GETs")
    args=ap.parse_args()
    if not args.execute:
        print("ZENODO_DRAFT_VALIDATION=DRY_RUN")
        return
    token=get_token()
    ok=True
    for role in ("preprint","fcg_dataset"):
        p=ROOT/"receipts"/f"{role}_draft.json"
        if not p.exists():
            print(f"{role.upper()}=MISSING_DRAFT_RECEIPT");ok=False;continue
        dep=json.loads(p.read_text())["deposition"]
        status,body=api_request("GET",dep["links"]["self"],token=token)
        print(f"{role.upper()}_GET_STATUS={status}")
        print(f"{role.upper()}_STATE={(body or {}).get('state')}")
        print(f"{role.upper()}_SUBMITTED={(body or {}).get('submitted')}")
        if status!=200: ok=False
    print(f"ZENODO_DRAFT_VALIDATION={'PASS' if ok else 'FAIL'}")
    raise SystemExit(0 if ok else 1)
if __name__=="__main__": main()
