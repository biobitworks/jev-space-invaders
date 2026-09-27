# 0-Vita-1 protocol specification (draft)

```
Vithia-S0 → VitaState → ContextPacket → Vithia-S1 → DecisionReceipt → ObservedTransition → successor VitaState
```

## Interfaces

Defined in `src/s01/protocol.py`.

- `System0Provider.compile(source, legal_actions, question) -> ContextPacket`
- `System1Provider.decide(packet) -> DecisionReceipt`
- `Observer.observe(packet, action) -> TransitionReceipt`

Private System-0 kernels plug in behind `OpaqueDeterministicSystem0Provider`. They return only approved public fields plus a sha256 commitment.

## Schemas

In `schemas/s01/`, JSON Schema 2020-12. The canonical representation is JSON, not MCP.

| File | Role |
|---|---|
| `S01_CONTEXT_PACKET_V1.json` | Context packet. Rejects `recommended_action`, `recommended_move`, `golden_action`, `best_action`; nested occurrences are rejected by `make_packet`. |
| `S01_DECISION_RECEIPT_V1.json` | Decision receipt. `probabilities` may be `NOT_AVAILABLE`, never fabricated. |
| `S01_TRANSITION_RECEIPT_V1.json` | Transition receipt. Requires `observation_status: OBSERVED` and an `ObservationReceipt`. |
| `S01_EXPERIMENT_RECEIPT_V1.json` | Experiment receipt. |
| `VITA_STATE_V1.json` | VitaState. |
| `VITA_TRAJECTORY_V1.json` | VitaTrajectory. |

## Canonical bytes

Defined in `src/s01/canon.py`.

- **Canonical JSON:** sort_keys, separators `(',', ':')`, UTF-8, NaN forbidden.
- **Content id:** `sha256:` plus the SHA-256 of the canonical bytes.
- **Address:** `src/kernels/address.py`. Reversible mixed-radix rank. An address is never a hash.

## Custody

- Atoms roll up to a breakpoint root, and breakpoint roots to the MMR (`docs/BREAKPOINT_PROTOCOL.md`).
- Verify with `python scripts/verify_breakpoints.py`.
- Custody establishes identity and inclusion only (`TYPE_ERROR_T5`).

## Type contract

`vita01/VITA01_TYPE_CONTRACT_V1.json` is enforced by `src/vita01/typecheck.py` and tested by `tests/test_type_errors.py`.

## Adapter surfaces

- Python: implemented.
- HTTP and CLI: specified by the same JSON Schemas; not implemented in this draft (NOT_TESTED).
- JavaScript, MCP, and a static verifier: deferred.
