#!/usr/bin/env python3
"""Independent verifier for the VITHIA-E2E-POSTSUBMISSION lineage: recomputes every atom hash, breakpoint
root, MMR leaf and MMR root from files on disk. Stored roots are never trusted. Usage: [--upto BP_ID]"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import vithia_e2e_lib as L

def main() -> int:
    upto = sys.argv[sys.argv.index("--upto") + 1] if "--upto" in sys.argv else None
    rows = L.verify_lineage(upto)
    for r in rows:
        print(f"{r['breakpoint_id']} verify={r['verify_state']} mmr_size={r['mmr_size']} recomputed={r['recomputed_root']} errors={r['errors']}")
    ok = bool(rows) and all(r["verify_state"] == "PASS" for r in rows)
    print("E2E_BREAKPOINT_VERIFY=" + ("PASS" if ok else "FAIL"))
    if rows:
        print(f"E2E_MMR_SIZE={rows[-1]['mmr_size']}\nE2E_MMR_ROOT={rows[-1]['recomputed_root']}")
    return 0 if ok else 1

if __name__ == "__main__":
    raise SystemExit(main())
