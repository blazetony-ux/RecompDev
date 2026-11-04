#!/usr/bin/env python3
"""Cross-ISA durable campaign launcher (see README-v0421.md)."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from campaign.resume import main
if __name__=='__main__':raise SystemExit(main())
