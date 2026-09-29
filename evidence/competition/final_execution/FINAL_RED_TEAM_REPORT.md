# Final Red Team Report

Created: 2026-09-28T21:15:21Z

## Findings

- 1P final capture is supported by 240 actual ALE RGB frames, verified frame roots, verified Ed25519 frame signatures, and playthrough MMR root `e55a47a7f16064477c4f101a38a849391c2fbc9f6557c5244daf0406b36dbd74`.
- 2P must remain `NOT_EXECUTED_ROM_GATE_BLOCKED`; no ROM licensing approval or ROM source provenance exists.
- Codex-side Mitosis final execution was performed: remember status `ok`, universal ID `agent:memories:47b923e2e5bf18083bbc05c3`, exact retrieval top result matched the new final memory.
- Codex-side Tenki final execution was attempted but blocked: local Tenki CLI reports the configured API key is invalid or revoked. Prior Tenki evidence remains prior-only.
- Browser/Playwright video was not produced. The canonical video is a deterministic replay render from verified frame FCOs, not a live execution capture.
- Frame Ed25519 signature verification does not imply Git commit signing. Signature domains are separate.
- Token and cost metrics are not applicable to the final scripted-policy run and are not inferred from FPS or video metadata.

## State

RED_TEAM_STATE=PASS_WITH_DISCLOSED_LIMITATIONS_AND_TENKI_CREDENTIAL_BLOCK
