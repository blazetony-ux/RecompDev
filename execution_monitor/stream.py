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

class LiveDisplaySampler:
    """Explicit, bounded live-view decimation; never alters disk evidence.

    All non-instruction events are forwarded (including input, stop, frame,
    watch summaries, capture-limit notices). The full observed instruction
    stream remains in the source-authenticated native JSONL evidence.
    """
    def __init__(self, publish, *, instruction_interval: int = 16):
        if not 1 <= instruction_interval <= 65536:
            raise ValueError('INVALID_DISPLAY_SAMPLE_INTERVAL')
        self.publish = publish
        self.instruction_interval = instruction_interval
        self.seen_instructions = 0
        self.suppressed_instructions = 0
        self.forwarded_events = 0

    def __call__(self, event):
        if event.get('type') == 'instruction':
            self.seen_instructions += 1
            if self.seen_instructions % self.instruction_interval != 1:
                self.suppressed_instructions += 1
                return False
        self.publish(event)
        self.forwarded_events += 1
        return True
