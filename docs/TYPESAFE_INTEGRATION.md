# TypeSafe integration — Vithia-Space

The supported integration surface is the TypeSafe Python SDK (`typesafe-sdk`) using `TypeSafeClient`. The client reads `TYPESAFE_API_KEY` from the environment and uses `jev-latest` by default.

Vithia-Space uses JEV only as a bounded action-decision service. Code owns environment state, action execution, logging, retries/fallback policy, and evidence custody.

## Public interface

- Input: minimum competition game-state representation.
- Question: one bounded Choice over legal Space Invaders actions for the pilot lane, if pilot is selected.
- Output: selected action, confidence/probability evidence, served model identity, and usage/latency metadata that the API exposes.

No secret or proprietary Vithia-family implementation detail is required for this interface.

Official references:
- https://docs.typesafe.ai/introduction/quickstart
- https://docs.typesafe.ai/api
- https://docs.typesafe.ai/primitives/choice
- https://docs.typesafe.ai/confidence
