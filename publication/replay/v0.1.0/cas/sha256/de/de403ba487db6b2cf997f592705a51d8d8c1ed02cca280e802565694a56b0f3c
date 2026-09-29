# Reproducibility

Canonical repository: biobitworks/jev-space-invaders

Scientific evidence-lock commit: 754945f572543452f6b9e3a21ccee16c175605af

Publication release-candidate source commit: d0062eb5776c1e96b68f445b4fbcafcb13fc3dc9

## Deterministic verification

    python -m pytest -q
    python scripts/secret_scan.py
    python scripts/verify_breakpoints.py
    python scripts/verify_episode_mmr.py
    python scripts/secondary_stats.py
    python scripts/verify_publication_breakpoints.py

## PDF build

    python scripts/build_manuscript.py
    tectonic -X compile publication/manuscript/main.tex --outdir publication/release/v0.1.0
    tectonic -X compile publication/supplement/supplement.tex --outdir publication/release/v0.1.0

Figures and tables are generated from governed frozen datasets and receipts. Manual numeric transcription is not used for figure/table generation.

## Known historical custody gap

The publication verifier distinguishes MMR-chain integrity from historical atom availability. For this release candidate, PUBLICATION_MMR_CHAIN_VERIFY is PASS and PUBLICATION_ATOM_REPLAY_VERIFY is PARTIAL because one ephemeral .pyc atom from VITA-PUB-BP-0015 is unavailable. The verifier exits with code 3 for this disclosed partial-replay state.
