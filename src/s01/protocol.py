"""S0<->S1 adapter protocol (public). System 0 compiles context; System 1 decides; an
Observer records the actual successor. System 0 never chooses the action.

Private System-0 kernels (Anticube math, ΔG*, Golden-Path ranking) are NOT in this
repository. They plug in as an OpaqueDeterministicSystem0Provider that returns only
approved public fields plus a sha256 commitment to its private context.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Protocol

from src.s01.canon import cbytes, content_id

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schemas" / "s01"
FORBIDDEN_KEYS = {"recommended_action", "recommended_move"}


class System0Provider(Protocol):
    name: str
    version: str

    def compile(self, source: dict, legal_actions: list[str], question: dict) -> dict: ...


class System1Provider(Protocol):
    def decide(self, packet: dict) -> dict: ...


class Observer(Protocol):
    def observe(self, packet: dict, action: str) -> dict: ...


def _walk_keys(o):
    if isinstance(o, dict):
        for k, v in o.items():
            yield k
            yield from _walk_keys(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk_keys(v)


def make_packet(domain: str, source_atoms: list[str], context: dict, legal_actions: list[str],
                question: dict, provider: dict, compile_ms: float, anticube: dict | None = None,
                path_summary: dict | None = None, private_commitment: str | None = None) -> dict:
    p = {"schema": "S01_CONTEXT_PACKET_V1", "domain": domain, "source_atoms": source_atoms,
         "context": context, "legal_actions": legal_actions, "question": question,
         "s0_provider": provider, "s0_compile_ms": round(compile_ms, 4)}
    if anticube is not None:
        p["anticube"] = anticube
    if path_summary is not None:
        p["path_summary"] = path_summary
    if private_commitment is not None:
        p["private_commitment"] = private_commitment
    bad = FORBIDDEN_KEYS & set(_walk_keys(p))
    if bad:
        raise ValueError(f"S0 packet may not carry {bad}: System 1 makes the decision")
    p["packet_id"] = content_id(p)
    return p


def validate(obj: dict, schema_name: str) -> None:
    import jsonschema

    schema = json.loads((SCHEMA_DIR / f"{schema_name}.json").read_text())
    jsonschema.validate(obj, schema)


def timed(fn, *a, **k):
    t0 = time.perf_counter()
    out = fn(*a, **k)
    return out, (time.perf_counter() - t0) * 1000.0


class OpaqueDeterministicSystem0Provider:
    """Adapter shell for a private S0 kernel living outside this repo (HTTP or CLI).
    Not implemented publicly; experiments that need it record NOT_TESTED."""
    name, version = "private-s0", "UNKNOWN"

    def compile(self, source, legal_actions, question):
        raise NotImplementedError("private System-0 provider is not part of the public repository")
