# Cross-host deterministic replication preregistration

Status: PROSPECTIVE_SUCCESSOR_REPLICATION.

Purpose: independently replay deterministic E0-E3 from the current frozen scientific predecessor on magicSTUDIObox and magicPRObox without rewriting historical results.

Primary comparison:
- exact input hashes
- exact source commit
- exact commands/runtime manifests
- output hash equality

Outcome vocabulary:
- BYTE_IDENTICAL
- SEMANTICALLY_IDENTICAL_NONBYTE
- MISMATCH_EXPLAINED
- MISMATCH_UNEXPLAINED
- DEFERRED_NOT_FAILED

E4A is verification-only: its frozen snapshot dataset must not be regenerated.
Historical breakpoints remain immutable.
