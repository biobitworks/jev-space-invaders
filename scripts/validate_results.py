#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.validate import check_file  # noqa: E402

s = check_file(ROOT / "results.json")
print("RESULTS_SCHEMA_CHECK=PASS")
for k, v in s.items():
    print(f"{k.upper()}={v}")
