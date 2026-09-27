"""Deciders. Each returns a Decision; the harness times every call and executes the action.

- ScriptedDecider: deterministic sweep, no model (harness smoke only; non-JEV).
- SystemOneHTTPDecider: POST /v1/systemone. TypeSafe JEV (hosted) or OpenJev (local);
  same request/response shape. Raw HTTP so retries and status codes are measured, not hidden.
- AdapterLLMDecider: LLM baseline through typesafe-ai/system-one-adapter, identical question.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from src.actions import ACTIONS

MOVE_QUESTION = {
    "type": "choice",
    "instructions": (
        "You control the player's laser cannon at the bottom of Space Invaders (`ship`). "
        "Choose the one action for the next 4 frames. Priorities in order: "
        "1) do not let any falling bomb in `bombs` reach the ship's x-range; "
        "2) shoot aliens (a new shot only fires if none of `own_shots` is still in flight); "
        "3) prefer positions under or near `shields` when bombs are close. "
        "RIGHT increases x, LEFT decreases x."
    ),
    "criteria": {
        "NOOP": "Stay in place without firing.",
        "FIRE": "Stay in place and fire straight up.",
        "RIGHT": "Move right (toward larger x) without firing.",
        "LEFT": "Move left (toward smaller x) without firing.",
        "RIGHTFIRE": "Move right while firing.",
        "LEFTFIRE": "Move left while firing.",
    },
}
RETRY_STATUS = {429, 500, 502, 503, 504, 520, 529}


@dataclass
class Decision:
    action: str
    proposed_action: str | None = None
    probabilities: dict | None = None
    confidence: float | None = None
    served_model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    model_call: bool = False
    retries: int = 0
    errors: dict = field(default_factory=dict)
    fallback: bool = False
    fallback_reason: str | None = None


class ScriptedDecider:
    role, provider, requested_model = "decider", "none", "scripted-policy"
    sdk_package, sdk_version = None, None

    def __init__(self, period: int = 30) -> None:
        self.period = period

    def decide(self, state: dict, prev_action: str) -> Decision:
        a = "RIGHTFIRE" if (state["step"] // self.period) % 2 == 0 else "LEFTFIRE"
        return Decision(action=a, proposed_action=a, served_model="scripted-policy")


class SystemOneHTTPDecider:
    """provider='typesafe' -> https://api.typesafe.ai, needs TYPESAFE_API_KEY.
    provider='openjev'  -> local helper shim (default http://127.0.0.1:3000), no key."""
    role = "decider"
    sdk_package, sdk_version = "none (raw HTTP)", None

    def __init__(self, provider: str, base_url: str | None = None, model: str | None = None,
                 max_retries: int = 3, timeout_s: float = 10.0) -> None:
        self.provider = provider
        if provider == "typesafe":
            self.url = (base_url or "https://api.typesafe.ai") + "/v1/systemone"
            self.requested_model = model or "jev-latest"
            key = os.environ.get("TYPESAFE_API_KEY")
            if not key:
                raise SystemExit("TYPESAFE_API_KEY not set (keep it in .env / environment, never in git)")
            self.headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
        elif provider == "openjev":
            self.url = (base_url or "http://127.0.0.1:3000") + "/v1/systemone"
            self.requested_model = model or "openjev"
            self.headers = {"Content-Type": "application/json"}
        else:
            raise ValueError(provider)
        self.max_retries, self.timeout_s = max_retries, timeout_s

    def decide(self, state: dict, prev_action: str) -> Decision:
        body = json.dumps({"state": state, "model": self.requested_model,
                           "questions": {"move": MOVE_QUESTION}}).encode()
        errors: dict[str, int] = {}
        for attempt in range(self.max_retries + 1):
            req = urllib.request.Request(self.url, data=body, headers=self.headers, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_s) as r:
                    resp = json.loads(r.read())
                ans = resp["answers"]["move"]
                usage = resp.get("usage") or {}
                choice = ans.get("choice")
                ok = choice in ACTIONS
                return Decision(action=choice if ok else prev_action, proposed_action=choice,
                                probabilities=ans.get("probabilities"), confidence=ans.get("confidence"),
                                served_model=resp.get("model"), input_tokens=usage.get("input_tokens"),
                                output_tokens=usage.get("output_tokens"), model_call=True,
                                retries=attempt, errors=errors, fallback=not ok,
                                fallback_reason=None if ok else "choice_not_in_action_set")
            except urllib.error.HTTPError as e:
                errors[str(e.code)] = errors.get(str(e.code), 0) + 1
                if e.code not in RETRY_STATUS:
                    break
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                errors["network"] = errors.get("network", 0) + 1
            time.sleep(min(2.0, 0.2 * 2 ** attempt))
        return Decision(action=prev_action, proposed_action=None, model_call=True,
                        retries=self.max_retries, errors=errors, fallback=True,
                        fallback_reason="request_failed_hold_previous_action")


class AdapterLLMDecider:
    role = "baseline"
    sdk_package = "system-one-adapter"

    def __init__(self, provider: str, model: str) -> None:
        from importlib.metadata import version

        from system_one_adapter import Choice, SystemOneAdapterClient

        self.provider, self.requested_model = provider, model
        self.sdk_version = version("system-one-adapter")
        self.client = SystemOneAdapterClient(structured_outputs=True, llm_answer_mode="probabilities",
                                             normalize_probabilities=True)
        self.question = {"move": Choice(instructions=MOVE_QUESTION["instructions"],
                                        criteria=MOVE_QUESTION["criteria"])}

    def decide(self, state: dict, prev_action: str) -> Decision:
        try:
            resp = self.client.system_one(state=state, questions=self.question,
                                          provider=self.provider, model=self.requested_model)
            d = resp.model_dump()
            ans, usage = d["answers"]["move"], d.get("usage") or {}
            choice = ans.get("choice")
            ok = choice in ACTIONS
            return Decision(action=choice if ok else prev_action, proposed_action=choice,
                            probabilities=ans.get("probabilities"), confidence=ans.get("confidence"),
                            served_model=d.get("model") or self.requested_model,
                            input_tokens=usage.get("input_tokens_total", usage.get("input_tokens")),
                            output_tokens=usage.get("output_tokens_total", usage.get("output_tokens")),
                            model_call=True, retries=int(usage.get("n_retries") or 0),
                            fallback=not ok, fallback_reason=None if ok else "choice_not_in_action_set")
        except Exception as e:  # provider failure: hold, and record the error class
            return Decision(action=prev_action, model_call=True, fallback=True,
                            errors={type(e).__name__: 1}, fallback_reason="adapter_error_hold_previous_action")

    def close(self) -> None:
        self.client.close()
