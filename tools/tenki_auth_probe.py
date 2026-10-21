#!/usr/bin/env python3
"""Smallest authenticated Tenki operation (Client.who_am_i). AUTH=PASS only on a real server response.
Runs under an interpreter that has the `tenki` SDK; the key travels only via the environment."""
import json, os, sys
try:
    from tenki import Client
except Exception as e:
    print(json.dumps({"TENKI_AUTH": "NOT_AVAILABLE", "error_class": f"SDK_IMPORT:{type(e).__name__}"})); sys.exit(3)
key = os.environ.get("TENKI_API_KEY", "")
if not key:
    print(json.dumps({"TENKI_AUTH": "BLOCKED", "error_class": "KEY_NOT_SET"})); sys.exit(2)
try:
    with Client(api_key=key) as c:
        ident = c.who_am_i()
    print(json.dumps({"TENKI_AUTH": "PASS", "owner_type": ident.owner_type, "workspace_count": len(ident.workspaces)}))
except Exception as e:  # noqa: BLE001
    msg = str(e).replace(key, "<redacted>")
    cls = "INVALID_OR_REVOKED_API_KEY" if any(w in msg.lower() for w in ("invalid", "revoked", "unauthenticated", "401")) else type(e).__name__
    print(json.dumps({"TENKI_AUTH": "BLOCKED" if cls.startswith("INVALID") else "FAIL", "error_class": cls})); sys.exit(1)
