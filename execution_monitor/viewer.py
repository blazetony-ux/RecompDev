"""Separate-process desktop subscriber to controller diagnostics v1.

Never opens a ROM, plugin DLL, game memory, or producer trace file. Closing this
window never pauses/stops the guest. The last view stays open after disconnect.
"""
from __future__ import annotations
import argparse
from collections import deque
import json
import queue
import socket
import threading
import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from controller.diagnostics import SCHEMA


def connect_and_stream(port: int, token: str, deliver):
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=10) as sock:
            sock.sendall((json.dumps({'schema': SCHEMA, 'token': token, 'role': 'subscribe'}) + '\n').encode())
            sock.settimeout(None)
            with sock.makefile('rb') as file:
                while True:
                    line = file.readline()
                    if not line:
                        break
                    try:
                        item = json.loads(line)
                        if isinstance(item, dict) and item.get('schema') == SCHEMA:
                            deliver(item)
                    except (ValueError, UnicodeError):
                        continue
    except OSError as exc:
        deliver({'type': 'notice', 'message': 'Controller connection failed: ' + str(exc)})
    finally:
        deliver({'type': 'session', 'status': 'Controller disconnected; last trace retained'})


class Viewer:
    def __init__(self, root: tk.Tk, port: int, token: str):
        self.root = root
        self.messages = queue.Queue(maxsize=2000)
        self.recent = deque(maxlen=350)
        self.root.title('RecompDev — Live Execution Monitor (Controller)')
        self.root.geometry('960x670')
        self.root.minsize(650, 420)
        self.info = tk.StringVar(value='Connecting to controller...')
        self.cpu = tk.StringVar(value='CPU: —     PC: —     SP: —     Steps: —')
        self.frame = tk.StringVar(value='Frame: —     Cycles: —     Input: —')
        self.stop = tk.StringVar(value='Status: starting')
        for var in (self.info, self.cpu, self.frame, self.stop):
            tk.Label(root, textvariable=var, font=('Consolas', 11), anchor='w').pack(fill='x', padx=12, pady=(8, 0))
        tk.Label(root, text='Instruction samples and events (not a full instruction-level disassembly)', anchor='w').pack(fill='x', padx=12, pady=(12, 3))
        self.text = ScrolledText(root, font=('Consolas', 10), wrap='none', state='disabled')
        self.text.pack(fill='both', expand=True, padx=12, pady=(0, 8))
        tk.Label(root, text='Read-only monitor. Close independently. Full bounded telemetry is saved in the evidence ZIP.', anchor='w').pack(fill='x', padx=12, pady=(0, 8))
        thread = threading.Thread(target=connect_and_stream, args=(port, token, self.enqueue), daemon=True)
        thread.start()
        root.after(80, self.refresh)

    def enqueue(self, item):
        try:
            self.messages.put_nowait(item)
        except queue.Full:
            try:
                self.messages.get_nowait()
            except queue.Empty:
                pass
            self.messages.put_nowait(item)

    def refresh(self):
        changed = False
        for _ in range(450):
            try:
                event = self.messages.get_nowait()
            except queue.Empty:
                break
            kind = event.get('type')
            if kind == 'connected':
                self.info.set('Connected to controller diagnostics interface v1')
            elif kind == 'instruction':
                pc = event.get('pc', 0)
                self.cpu.set(f"CPU: {event.get('cpu', '?')}   PC: {pc:#06x}   SP: {event.get('sp', 0):#06x}   Steps: {event.get('steps', 0):,}")
                self.recent.append(f"{event.get('guest_cycles', 0):>12}  {pc:04X}  opcode {event.get('opcode', 0):02X}  {event.get('opcode_class', '?'):<24} -> {event.get('next_pc', 0):04X}")
                changed = True
            elif kind == 'frame':
                self.frame.set(f"Frame: {event.get('frame', 0)}     Cycles: {event.get('guest_cycles', 0):,}     Steps: {event.get('steps', 0):,}")
            elif kind == 'input':
                self.frame.set(self.frame.get().split('     Input:')[0] + f"     Input mask: {event.get('buttons', 0):#x}")
                self.recent.append('INPUT ' + str(event))
                changed = True
            elif kind in ('stop', 'notice', 'session'):
                if kind == 'session' and str(event.get('status', '')).startswith('Controller disconnected'):
                    self.info.set('Controller disconnected — last events retained; close this window when ready')
                elif kind == 'stop':
                    self.stop.set('Guest stopped: ' + str(event.get('status', '?')) + ' @ ' + hex(event.get('pc', 0)))
                else:
                    self.stop.set('Status: ' + str(event.get('status', event.get('message', kind))))
                self.recent.append(kind.upper() + ' ' + str(event))
                changed = True
        if changed:
            self.text.configure(state='normal')
            self.text.delete('1.0', 'end')
            self.text.insert('end', '\n'.join(self.recent) + '\n')
            self.text.see('end')
            self.text.configure(state='disabled')
        self.root.after(80, self.refresh)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--port', type=int, required=True)
    p.add_argument('--token', required=True)
    opts = p.parse_args()
    root = tk.Tk()
    Viewer(root, opts.port, opts.token)
    root.mainloop()

if __name__ == '__main__':
    main()
