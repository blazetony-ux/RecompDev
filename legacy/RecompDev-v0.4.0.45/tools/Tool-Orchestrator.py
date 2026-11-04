#!/usr/bin/env python3
"""Stable entrypoint for game-independent tool orchestration."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tooling.orchestrator import main
if __name__=='__main__':sys.exit(main())
