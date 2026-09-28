"""Local-Ollama LLM baseline decider (role='baseline'), for use when no hosted
provider key is available. NOT the System One adapter path used by AdapterLLMDecider:
no calibrated probabilities, no cloud SDK. Honestly labeled provider='ollama' so
results.json and README never conflate this with the documented cloud-provider baseline.
"""
from __future__ import annotations
import json, time, urllib.error, urllib.request

from src.actions import ACTIONS
from src.deciders import Decision, MOVE_QUESTION, RETRY_STATUS
from src.s01.protocol import FORBIDDEN_KEYS

ACTION_SCHEMA = {"type": "object", "properties": {"choice": {"type": "string", "enum": list(ACTIONS)}},
                  "required": ["choice"], "additionalProperties": False}


def _keys(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k
            yield from _keys(v)
    elif isinstance(o, list):
        for v in o:
            yield from _keys(v)


class OllamaBaselineDecider:
    role = "baseline"
    provider = "ollama"
    sdk_package = "ollama-http"
    sdk_version = None

    def __init__(self, model: str, base_url: str = "http://127.0.0.1:11434",
                 timeout_s: float = 60.0, max_retries: int = 2) -> None:
        self.requested_model = model
        self.url = base_url.rstrip("/") + "/api/generate"
        self.timeout_s, self.max_retries = timeout_s, max_retries
        self.headers = {"Content-Type": "application/json"}

    def _body(self, context: dict) -> bytes:
        bad = FORBIDDEN_KEYS & set(_keys(context))
        if bad:
            raise ValueError(f"decision leakage: {sorted(bad)}")
        prompt = ("You are the LLM baseline decider for Space Invaders. Choose exactly one legal action. "
                  "Return only the required JSON object.\nQUESTION=" +
                  json.dumps(MOVE_QUESTION, sort_keys=True, separators=(",", ":")) +
                  "\nSTATE=" + json.dumps(context, sort_keys=True, separators=(",", ":")))
        obj = {"model": self.requested_model, "prompt": prompt, "stream": False, "format": ACTION_SCHEMA,
               "options": {"temperature": 0, "seed": 0, "num_predict": 32}}
        return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()

    def decide(self, state: dict, prev_action: str) -> Decision:
        body = self._body(state)
        errors: dict[str, int] = {}
        for attempt in range(self.max_retries + 1):
            req = urllib.request.Request(self.url, data=body, headers=self.headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_s) as r:
                    resp = json.loads(r.read())
                try:
                    ans = json.loads(resp.get("response") or "{}")
                except Exception:
                    ans = {}
                choice = ans.get("choice")
                ok = choice in ACTIONS
                return Decision(action=choice if ok else prev_action, proposed_action=choice,
                                probabilities=None, confidence=None,
                                served_model=resp.get("model") or self.requested_model,
                                input_tokens=resp.get("prompt_eval_count"), output_tokens=resp.get("eval_count"),
                                model_call=True, retries=attempt, errors=errors, fallback=not ok,
                                fallback_reason=None if ok else "choice_not_in_action_set")
            except urllib.error.HTTPError as e:
                errors[str(e.code)] = errors.get(str(e.code), 0) + 1
                if e.code not in RETRY_STATUS:
                    break
            except (urllib.error.URLError, TimeoutError, OSError):
                errors["network"] = errors.get("network", 0) + 1
            time.sleep(min(2.0, 0.2 * 2 ** attempt))
        return Decision(action=prev_action, model_call=True, retries=self.max_retries, errors=errors,
                        fallback=True, fallback_reason="request_failed_hold_previous_action")
