"""Reversible state addressing (Library-of-Babel-style design precedent, clean-room).

A state is a fixed-length sequence over an alphabet of size k. Its ADDRESS is its
mixed-radix rank in [0, k**n); unrank inverts it exactly. The address is an index into
an implicit space, not a digest: it is reversible and carries no integrity guarantee.
The CONTENT_ID (SHA-256 of canonical bytes) is separate, one-way, and never used as an
address. ADDRESS != HASH.
"""
from __future__ import annotations

import hashlib

B32 = "0123456789abcdefghjkmnpqrstvwxyz"  # Crockford base32 alphabet (lowercase)


def rank(state: list[int], k: int) -> int:
    a = 0
    for s in state:
        if not 0 <= s < k:
            raise ValueError("symbol out of alphabet")
        a = a * k + s
    return a


def unrank(address: int, k: int, n: int) -> list[int]:
    if not 0 <= address < k ** n:
        raise ValueError("address out of space")
    out = [0] * n
    for i in range(n - 1, -1, -1):
        address, out[i] = divmod(address, k)
    return out


def address_str(address: int, k: int, n: int) -> str:
    """Fixed-width base32 rendering, prefixed with the space it indexes."""
    width = max(1, -(-((k ** n) - 1).bit_length() // 5))
    digits = []
    for _ in range(width):
        address, r = divmod(address, 32)
        digits.append(B32[r])
    return f"k{k}n{n}:" + "".join(reversed(digits))


def parse_address(s: str) -> tuple[int, int, int]:
    head, body = s.split(":")
    k, n = (int(x) for x in head[1:].split("n"))
    a = 0
    for ch in body:
        a = a * 32 + B32.index(ch)
    return a, k, n


def canonical_state_bytes(state: list[int], k: int) -> bytes:
    if k > 256:
        raise ValueError("canonical byte form defined for k <= 256")
    return f"S01STATE:k={k}:n={len(state)}:".encode() + bytes(state)


def state_content_id(state: list[int], k: int) -> str:
    return "sha256:" + hashlib.sha256(canonical_state_bytes(state, k)).hexdigest()
