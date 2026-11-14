"""Stable entrypoint for the compiled RecompDev controller."""
from standalone_export.exporter import main
if __name__=='__main__':
    raise SystemExit(main())
