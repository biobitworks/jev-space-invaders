from __future__ import annotations
import json, sys, urllib.request
from pathlib import Path

ENTRY = Path(__file__).resolve().parents[1] / 'entry.local.json'
URL = 'https://mitosislabs.ai/api/ufa/jev/entries'

if not ENTRY.exists():
    raise SystemExit('entry.local.json missing; create it locally and do not commit it')
payload = json.loads(ENTRY.read_text())
payload['submitted_via'] = 'api'
req = urllib.request.Request(URL, data=json.dumps(payload).encode(), headers={'Content-Type':'application/json'}, method='POST')
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.loads(r.read().decode())
except Exception as e:
    raise SystemExit(f'SUBMISSION_HTTP_ERROR={e}')
print(json.dumps(body, indent=2))
if body.get('ok') is not True:
    raise SystemExit(2)
