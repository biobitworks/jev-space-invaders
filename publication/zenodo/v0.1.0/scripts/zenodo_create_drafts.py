#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path
from zenodo_common import api_request, dump_receipt, get_token, load_ready_metadata

ROOT=Path(__file__).resolve().parents[1]
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--base-url",default="https://sandbox.zenodo.org")
    ap.add_argument("--execute",action="store_true")
    ap.add_argument("--reserve-doi",action="store_true")
    args=ap.parse_args()
    specs=[
      ("preprint",ROOT/"metadata"/"zenodo_metadata_preprint.json"),
      ("fcg_dataset",ROOT/"metadata"/"zenodo_metadata_fcg_dataset.json"),
    ]
    for role,path in specs:
        try:
            meta=load_ready_metadata(path)
        except SystemExit as e:
            print(f"{role.upper()}_DRAFT=BLOCKED {e}")
            continue
        if args.reserve_doi:
            meta["prereserve_doi"]=True
        print(json.dumps({"role":role,"endpoint":args.base_url.rstrip("/")+"/api/deposit/depositions","metadata":meta},indent=2))
        if not args.execute:
            print(f"{role.upper()}_DRAFT=DRY_RUN")
            continue
        token=get_token()
        status,body=api_request("POST",args.base_url.rstrip("/")+"/api/deposit/depositions",token=token,json_body={"metadata":meta})
        receipt={"schema":"VITHIA_ZENODO_DRAFT_RECEIPT_V1","role":role,"http_status":status,"deposition":body}
        dump_receipt(ROOT/"receipts"/f"{role}_draft.json",receipt)
        doi=((body or {}).get("metadata") or {}).get("prereserve_doi",{}).get("doi")
        print(f"{role.upper()}_DRAFT=CREATED")
        print(f"{role.upper()}_DEPOSITION_ID={(body or {}).get('id')}")
        print(f"{role.upper()}_RESERVED_DOI={doi or 'NOT_RESERVED'}")
if __name__=="__main__": main()
