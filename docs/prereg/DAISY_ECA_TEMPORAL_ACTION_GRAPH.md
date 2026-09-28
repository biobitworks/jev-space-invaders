# Daisy ECA Temporal Action Graph V1 — prospective protocol

Purpose: preserve the unique reachable control graph over time for all 256 ECA hazard rules while keeping the ECA rule itself distinct from the intervention policy.

Frozen parameters:
- world: existing deterministic CA-dodge V1, width 16, periodic ECA;
- rules: 0..255;
- initial-condition families: single, rand1=11, rand2=12, rand3=13;
- starts: columns 4, 8, 12;
- actions: LEFT, STAY, RIGHT;
- horizon: 8 decisions;
- collision: next hazard row has bit 1 at the post-action ship column;
- collision branches terminate;
- exact transposition: same rule-generated hazard row, ship position and decision depth;
- each graph row stores path multiplicity to the parent state and one outgoing action;
- graph edges plus path multiplicities represent the full raw action-string space without row-level duplication;
- quality target: number of full-horizon safe completions downstream of each action;
- public Anticube: deterministic operator-declared identity x safety labels only;
- model-free U* is 0 when at least one safe continuation exists, else 1;
- H_norm, G* and DeltaG* are NOT_COMPUTED in model-free rows;
- DeltaG* may only appear later in a separate OpenJev augmentation using a frozen definition and observed probabilities;
- split policy is inherited from the Daisy ECA corpus and holds out complete structural families.

Output classification: TRAINING_CANDIDATE. It is not an E0-E4 evaluation dataset, not a trained model, and not VITHIA_NATIVE.

