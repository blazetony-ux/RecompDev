"""Versioned, host-independent standalone packaging contracts.

The controller is only the orchestration entrypoint. Source adapters own all
CPU/machine-specific project layouts; the package builder never decodes an ISA.
"""
