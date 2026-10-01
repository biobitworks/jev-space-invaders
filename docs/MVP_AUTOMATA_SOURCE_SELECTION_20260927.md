# MVP prior-art intake: Library of Babel, Minesweeper, and cellular automata

**Intake ID:** `VITHIA_SPACE_AUTOMATA_MVP_SOURCE_INTAKE_20260927_001`  
**State:** bounded candidate evidence; no canonical scientific mutation  
**Parent repo commit:** `3095964e6a4fd898f52647f62a625c07e7c44165`  
**Third-party code vendored:** NO

## MVP decision

Use the upstream projects as **prior art and validation references**, not as mandatory runtime dependencies.

| Layer | Preferred reference | MVP implementation |
|---|---|---|
| Reversible state addressing | `louis-e/LibraryOfBabel-Python@15fe2c8...` (MIT) | Minimal in-repo canonical rank/unrank codec |
| Minesweeper constraint inference | `jwang541/Minesweeper-Solver-SAT@9bdb1c3...` (MIT) | Minimal local constraint layer; optional SAT verification |
| Elementary CA | `lantunes/cellpylib@743e936...` (Apache-2.0; JOSS DOI 10.21105/joss.03608) | Minimal deterministic ECA rules 0–255 in-repo |

## Why these are more relevant than directly importing the topic-page examples

The GitHub topic pages are mutable discovery indices. They are useful for prior-art discovery but are poor runtime dependencies because their membership changes.

`CellPyLib` is a stronger CA reference because it is tested, supports elementary CA directly, exposes entropy/complexity functions, has an Apache-2.0 license, and has a JOSS publication. For the competition MVP, however, generating all 256 elementary rules requires only a very small deterministic kernel. Keeping that kernel inside the repository makes replay, hashing, tests, and containerization simpler.

The browser implementation at `nickarocho/minesweeper` is useful for classic board/cell semantics and presentation, but no root license file was recovered. Therefore code reuse is **ABSTAIN**. The SAT solver repository is more directly relevant to Vithia's hidden-hazard layer because it explicitly maps revealed clues into Boolean constraints and identifies safe/mine/unresolved states.

The Library-of-Babel Python implementation demonstrates reversible content ↔ address mapping and is MIT licensed. For Vithia-Space, use that as design precedent and implement a smaller domain-specific reversible state address instead of importing page/hexagon semantics wholesale.

## Intended Vithia-Space mapping

```
ALE frame/state
  -> atom extraction
  -> CA hazard projection
  -> Minesweeper-style local constraints
  -> candidate paths / path weights
  -> JEV decision

canonical state bytes
  <-> reversible state address
  -> content hash (separate identity operation)
  -> FCO/FCG receipt
```

Do not conflate:

- reversible state address with cryptographic hash;
- Minesweeper with cellular automata;
- CA/path scores with thermodynamic Gibbs energy;
- source citation with scientific validation.

## Integration gate

Before vendoring or copying any third-party source:

1. verify exact upstream commit;
2. verify license/NOTICE obligations;
3. copy only what is needed;
4. preserve attribution;
5. record exact imported bytes;
6. compute SHA-256 if those bytes become load-bearing;
7. update `THIRD_PARTY_NOTICES.md`;
8. create a new evidence breakpoint.

Until then these remain source/reference FCO candidates only.
