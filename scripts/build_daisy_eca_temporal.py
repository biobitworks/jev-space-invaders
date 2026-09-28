#!/usr/bin/env python3
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from src.daisy.eca_temporal_corpus import build
if __name__=="__main__":
    print(build())

