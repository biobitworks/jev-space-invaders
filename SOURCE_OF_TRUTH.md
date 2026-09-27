# Vithia-Space starting source of truth

## Frozen executable evidence dataset

`VITHIA_SPACE_RUNTIME_SOURCE_FREEZE_20260927_001` is the initial runtime-source dataset for Vithia-Space. It treats executable environment information as data because runtime bytes and state transitions can influence experimental behavior, safety, and security.

FMO root: `28c9beac8c617df2c8409b50d45ee6240408455c53db5b845261fb4005171a81`

Frozen privately and hash-committed publicly: PettingZoo 1.27.0 source/archive/docs, the Python 3.14 arm64 dependency wheels selected for `pettingzoo[atari]==1.27.0`, and their exact byte hashes.

The Space Invaders ROM is **not present** and no ROM license acceptance was performed. No game execution is admitted under this breakpoint.

Unknown runtime information remains first-class `RuntimeUnknownFCO` state; it is never converted to PASS.

## Dataset succession

Future episode datasets must bind their parent runtime FMO root, environment configuration, seed, observation projection, agent/model identity, decision policy, and exact transition log. Corrections create successor datasets; they do not overwrite this freeze.

## Claim ceiling

This freeze proves byte identity and declared relationships only. It is not evidence that the runtime is safe, secure, correct, or causally responsible for any future model behavior.
