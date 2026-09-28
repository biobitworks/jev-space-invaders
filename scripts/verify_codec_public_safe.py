#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODEC_DIR = ROOT / "evidence/competition/codec"
FORBIDDEN_PATTERNS = [
    ("PRIVATE_KEY", re.compile(r"BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY")),
    ("OPENAI_STYLE_KEY", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("BEARER_TOKEN", re.compile(r"Bearer\s+[A-Za-z0-9._~-]{20,}", re.I)),
    ("PLACEMENT_ALGORITHM", re.compile(r"placement algorithm", re.I)),
    ("ECC_TUNING", re.compile(r"ECC tuning", re.I)),
    ("SHARD_SCHEDULE", re.compile(r"shard schedule", re.I)),
    ("ROBUST_CHANNEL_PARAMETERS", re.compile(r"robust-channel|robust channel parameters", re.I)),
    ("PRIVATE_DECODER", re.compile(r"private decoder", re.I)),
    ("PRIVATE_EXTRACTOR", re.compile(r"private extractor", re.I)),
]


def main() -> int:
    hits: list[tuple[str, str]] = []
    checked = 0
    for path in sorted(CODEC_DIR.glob("*")):
        if not path.is_file():
            continue
        checked += 1
        text = path.read_text(errors="ignore")
        if path.suffix == ".json":
            json.loads(text)
        elif path.suffix == ".jsonl":
            for line in text.splitlines():
                if line.strip():
                    json.loads(line)
        for name, pattern in FORBIDDEN_PATTERNS:
            if pattern.search(text):
                hits.append((str(path.relative_to(ROOT)), name))
    print("CODEC_PUBLIC_SAFE_VERIFY=" + ("PASS" if not hits else "FAIL"))
    print("CODEC_PUBLIC_SAFE_FILES_CHECKED=" + str(checked))
    for hit in hits:
        print("HIT=" + repr(hit))
    return 0 if not hits else 2


if __name__ == "__main__":
    raise SystemExit(main())
