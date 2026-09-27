# Vithia-Space piecewise comparison plan

Parent runtime FMO: `28c9beac8c617df2c8409b50d45ee6240408455c53db5b845261fb4005171a81`

All arms share the same admitted runtime source dataset and fixed seeds unless an explicit successor changes the substrate.

| Arm | Decision/state design | State |
|---|---|---|
| R0 | deterministic/simple scripted policy | PROPOSED |
| J0 | JEV + current state only | PROPOSED |
| J1 | JEV + compact temporal state | PROPOSED |
| J2 | JEV + FCG-addressed temporal memory | PROPOSED |
| L0 | matched state + LLM/System One adapter | PROPOSED |
| V0 | Vithia-Space piecewise decision layer over the same admitted projections | PROPOSED / NOT_TRAINED |

`V0` must not train on JEV outputs. JEV responses may be retained as benchmark evidence only. Any Vithia-Space training dataset must be independently constructed from admitted environment observations/outcomes or other licensed sources and receive its own DatasetFCO/FMO root.

Primary decomposition: environment/runtime contribution vs state-projection contribution vs decision-model contribution vs temporal/FCG-memory contribution. FCG edges declare relationships; they do not by themselves establish causality.
