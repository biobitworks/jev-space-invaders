"""OpenJev client for the PettingZoo Space Invaders action ontology.

Separate from src/openjev_client.py because ALE and PZ action byte 2 have different
semantics. This module is intended only for the unfrozen E5 2P successor.
"""
from __future__ import annotations
import json, time, urllib.error, urllib.request
from src.deciders import Decision, RETRY_STATUS
from src.openjev_client import OpenJevDecider

PZ_ACTIONS=("NOOP","FIRE","UP","RIGHT","LEFT","DOWN")

class PZOpenJevDecider(OpenJevDecider):
    def decide_body(self, body:bytes, prev_action:str)->Decision:
        errors={}
        for attempt in range(self.max_retries+1):
            req=urllib.request.Request(self.url,data=body,headers=self.headers,method="POST")
            try:
                with urllib.request.urlopen(req,timeout=self.timeout_s) as r:
                    resp=json.loads(r.read())
                ans,usage=resp["answers"]["move"],resp.get("usage") or {}
                choice=ans.get("choice")
                ok=choice in PZ_ACTIONS
                return Decision(action=choice if ok else prev_action,proposed_action=choice,
                    probabilities=ans.get("probabilities"),confidence=ans.get("confidence"),
                    served_model=resp.get("model"),input_tokens=usage.get("input_tokens"),
                    output_tokens=usage.get("output_tokens"),model_call=True,retries=attempt,
                    errors=errors,fallback=not ok,
                    fallback_reason=None if ok else "choice_not_in_pz_action_set")
            except urllib.error.HTTPError as exc:
                errors[str(exc.code)]=errors.get(str(exc.code),0)+1
                if exc.code not in RETRY_STATUS:
                    break
            except (urllib.error.URLError,TimeoutError,OSError):
                errors["network"]=errors.get("network",0)+1
            time.sleep(min(2.0,0.2*2**attempt))
        return Decision(action=prev_action,model_call=True,retries=self.max_retries,
            errors=errors,fallback=True,fallback_reason="request_failed_hold_previous_action")

