# 0-Vita-1 biological translation contract (design only)

`CURRENT_IN_VITRO_EXECUTION=NO` · `CURRENT_IN_VIVO_EXECUTION=NO` · `BIOLOGICAL_TRANSFER_SUPPORTED=NO`

The protocol structure is the same at every evidence layer; **the evidence classes are not interchangeable**.

| Layer | Source | S0 → VitaState → ContextPacket | Decision | Observation |
|---|---|---|---|---|
| Computational (now) | simulator state / frames | yes | model decision | simulator transition (SIMULATED) |
| In vitro (future) | measured cellular/molecular state | yes | intervention hypothesis | controlled cell/tissue experiment → measured endpoint (IN_VITRO) |
| In vivo (future) | measured organism state | yes | intervention hypothesis | ethically/legally governed intervention or observational study → organism endpoint (IN_VIVO) |

**Required mapping fields for any future biological VitaState:**

- `simulation_source_ref`, `biological_system`, `experimental_model`
- `intervention`, `dose_or_intensity`, `timepoint`
- `measurement_assay`, `endpoint_definition`
- `control_group`, `replicate_definition`
- `observation_receipt`, `evidence_level`

**Enforced rule** (`src/vita01/typecheck.py`, TYPE_ERROR_T3): evidence level increases only with an `ObservationReceipt` whose `evidence_level` equals the target level. A SIMULATED prediction can motivate an in-vitro experiment; it cannot become an in-vitro observation.
