# E5 PettingZoo OpenJev Client V2

State: IMPLEMENTATION_ONLY_UNTIL_E5_PREREG.

This add-only successor corrects an unfrozen implementation mismatch discovered before scientific E5 calls.

The generic OpenJev client validates choices against the ALE ontology:
NOOP, FIRE, RIGHT, LEFT, RIGHTFIRE, LEFTFIRE.

PettingZoo Space Invaders uses a distinct ontology:
NOOP, FIRE, UP, RIGHT, LEFT, DOWN.

Therefore E5 2P must use `PZOpenJevDecider`, which preserves the same OpenJev HTTP retry/error accounting but validates System-1 choices against the PZ ontology. In particular, UP and DOWN are valid PZ decisions and must not fall back merely because they are absent from ALE.

No historical file is changed. This supplement must be atomized by the E5 prereg before any 2P scientific call.

The E5 prereg must also require an explicit wall-clock budget and retains governed DeltaG* as NOT_COMPUTED.

