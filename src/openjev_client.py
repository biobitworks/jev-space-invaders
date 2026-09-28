"""Local OpenJev client for E4B. Extends the sealed SystemOneHTTPDecider (src/deciders.py is a BP-0010
atom and must not change): adds the local shim bearer token and exact-request-bytes calls."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from src.actions import ACTIONS
from src.deciders import MOVE_QUESTION, RETRY_STATUS, Decision, SystemOneHTTPDecider


class OpenJevDecider(SystemOneHTTPDecider):
    def __init__(self, base_url: str, model: str = "openjev", **kw):
        super().__init__("openjev", base_url, model, **kw)
        tokf = Path.home() / ".openjev" / "token"
        tok = os.environ.get("OPENJEV_TOKEN") or (tokf.read_text().strip() if tokf.exists() else "")
        if tok:
            self.headers["Authorization"] = f"Bearer {tok}"

    def request_body(self, context: dict) -> bytes:
        return json.dumps({"state": context, "model": self.requested_model, "questions": {"move": MOVE_QUESTION}}).encode()

    def decide_body(self, body: bytes, prev_action: str) -> Decision:
        """Same retry/error accounting as SystemOneHTTPDecider.decide, over exact request bytes."""
        errors: dict[str, int] = {}
        for attempt in range(self.max_retries + 1):
            req = urllib.request.Request(self.url, data=body, headers=self.headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_s) as r:
                    resp = json.loads(r.read())
                ans, usage = resp["answers"]["move"], resp.get("usage") or {}
                choice = ans.get("choice")
                ok = choice in ACTIONS
                return Decision(action=choice if ok else prev_action, proposed_action=choice,
                                probabilities=ans.get("probabilities"), confidence=ans.get("confidence"),
                                served_model=resp.get("model"), input_tokens=usage.get("input_tokens"),
                                output_tokens=usage.get("output_tokens"), model_call=True, retries=attempt,
                                errors=errors, fallback=not ok, fallback_reason=None if ok else "choice_not_in_action_set")
            except urllib.error.HTTPError as e:
                errors[str(e.code)] = errors.get(str(e.code), 0) + 1
                if e.code not in RETRY_STATUS:
                    break
            except (urllib.error.URLError, TimeoutError, OSError):
                errors["network"] = errors.get("network", 0) + 1
            time.sleep(min(2.0, 0.2 * 2 ** attempt))
        return Decision(action=prev_action, model_call=True, retries=self.max_retries, errors=errors,
                        fallback=True, fallback_reason="request_failed_hold_previous_action")
