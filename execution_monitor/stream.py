"""Append-only native event bridge into controller's single diagnostic interface.

The native producer writes typed events to an evidence file. This adapter feeds
controller-owned fan-out; the GUI never reads the producer file or CPU plugins.
"""
from __future__ import annotations
import json
from pathlib import Path
from controller.diagnostics import normalize

class NativeEventReader:
    def __init__(self, path: Path, publish):
        self.path = Path(path)
        self.publish = publish
        self.offset = 0
        self.pending = b''
        self.delivered = 0
        self.rejected = 0

    def poll(self):
        if not self.path.is_file():
            return 0
        with self.path.open('rb') as handle:
            handle.seek(self.offset)
            raw = handle.read(262144)
            self.offset = handle.tell()
        self.pending += raw
        if len(self.pending) > 524288:
            raise ValueError('Unterminated native telemetry record exceeded limit')
        produced = 0
        while b'\n' in self.pending:
            line, self.pending = self.pending.split(b'\n', 1)
            if not line:
                continue
            try:
                event = normalize(json.loads(line))
            except (UnicodeError, json.JSONDecodeError, ValueError):
                self.rejected += 1
                continue
            self.publish(event)
            self.delivered += 1
            produced += 1
        return produced
