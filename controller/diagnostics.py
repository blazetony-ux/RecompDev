"""Controller-owned, CPU-neutral live diagnostics interface (v1).

The execution monitor ONLY subscribes here. Guest adapters send typed events to
controller orchestration, never to the viewer. Localhost + unpredictable session
secret; no inbound 'control' or untrusted publishers. Bounded fan-out and history.
"""
from __future__ import annotations
from collections import deque
import json
import queue
import secrets
import socket
import socketserver
import threading
from typing import Any

SCHEMA = 'recompdev.controller.diagnostics.v1'
EVENT_TYPES = frozenset(('session', 'instruction', 'frame', 'input', 'hardware', 'stop', 'native_result', 'notice', 'watch_summary'))
MAX_EVENT_BYTES = 4096


def normalize(event: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(event, dict) or event.get('type') not in EVENT_TYPES:
        raise ValueError('Unsupported diagnostics event')
    encoded = json.dumps(event, separators=(',', ':'), ensure_ascii=True, allow_nan=False)
    if len(encoded.encode('ascii')) > MAX_EVENT_BYTES:
        raise ValueError('Diagnostics event too large')
    # Strictly JSON-safe, no user-provided executable data or remote links.
    return json.loads(encoded)


class _TCP(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = False
    daemon_threads = True


class ControllerDiagnostics:
    """One controller-facing publication API and one viewer subscription ABI."""
    def __init__(self, *, history_limit: int = 512, subscriber_limit: int = 4):
        self.token = secrets.token_hex(24)
        self._lock = threading.RLock()
        self._history = deque(maxlen=history_limit)
        self._subscribers: list[queue.Queue] = []
        self._subscriber_drops: dict[queue.Queue, int] = {}
        self._subscriber_limit = subscriber_limit
        self._sequence = 0
        owner = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                self.connection.settimeout(5)
                try:
                    greeting = self.rfile.readline(2048)
                    request = json.loads(greeting)
                    if request.get('schema') != SCHEMA or request.get('token') != owner.token or request.get('role') != 'subscribe':
                        return
                    channel = queue.Queue(maxsize=256)
                    with owner._lock:
                        if len(owner._subscribers) >= owner._subscriber_limit:
                            return
                        for event in owner._history:
                            if channel.full():
                                channel.get_nowait()
                            channel.put_nowait(event)
                        owner._subscribers.append(channel)
                        owner._subscriber_drops[channel] = 0
                    last_drop_notice = 0
                    self.connection.settimeout(1)
                    try:
                        self.wfile.write((json.dumps({'schema': SCHEMA, 'type': 'connected'}) + '\n').encode())
                        self.wfile.flush()
                        while not owner._closed.is_set():
                            try:
                                event = channel.get(timeout=0.5)
                            except queue.Empty:
                                continue
                            with owner._lock:
                                dropped = owner._subscriber_drops.get(channel, 0)
                            if dropped > last_drop_notice:
                                # This counts display transport losses only.
                                # The on-disk native telemetry evidence is separate.
                                notice = {'schema': SCHEMA, 'type': 'notice',
                                          'message': 'Display transport dropped samples',
                                          'display_dropped': dropped}
                                self.wfile.write((json.dumps(notice, separators=(',', ':')) + '\n').encode())
                                last_drop_notice = dropped
                            self.wfile.write((json.dumps(event, separators=(',', ':')) + '\n').encode())
                            self.wfile.flush()
                    finally:
                        with owner._lock:
                            if channel in owner._subscribers:
                                owner._subscribers.remove(channel)
                            owner._subscriber_drops.pop(channel, None)
                except (OSError, json.JSONDecodeError, ValueError):
                    return

        self._server = _TCP(('127.0.0.1', 0), Handler)
        self._closed = threading.Event()
        self.port = self._server.server_address[1]
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True, name='controller-diagnostics')
        self._thread.start()

    @property
    def subscribers(self):
        with self._lock:
            return len(self._subscribers)

    def publish(self, event: dict[str, Any]):
        data = normalize(event)
        with self._lock:
            self._sequence += 1
            data['sequence'] = self._sequence
            data['schema'] = SCHEMA
            self._history.append(data)
            for channel in self._subscribers:
                if channel.full():
                    channel.get_nowait()
                    self._subscriber_drops[channel] = self._subscriber_drops.get(channel, 0) + 1
                channel.put_nowait(data)

    def close(self):
        if self._closed.is_set():
            return
        self._closed.set()
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(timeout=2)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
