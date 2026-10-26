"""The only module that runs PipeWire tools. Everything goes through subprocess."""
from __future__ import annotations

import ctypes
import json
import os
import select
import shutil
import signal
import subprocess
import threading
import time
from pathlib import Path


class PipeWireError(RuntimeError):
    pass


def require_tools() -> None:
    missing = [t for t in ("pipewire", "pw-cli", "pw-dump", "wpctl", "pw-metadata") if not shutil.which(t)]
    if missing:
        raise PipeWireError("missing PipeWire tools: " + ", ".join(missing))


def pw_dump(*args: str, timeout: float = 5.0) -> list[dict]:
    out = subprocess.run(["pw-dump", "-N", *args], capture_output=True, text=True, timeout=timeout)
    if out.returncode != 0:
        raise PipeWireError(out.stderr.strip() or "pw-dump failed")
    try:
        return json.loads(out.stdout or "[]")
    except ValueError as e:
        raise PipeWireError(f"pw-dump returned invalid JSON: {e}") from e


def node_props(obj: dict) -> dict:
    return (obj.get("info") or {}).get("props") or {}


def find_node(name: str, dump: list[dict] | None = None) -> int | None:
    for o in dump if dump is not None else pw_dump():
        if o.get("type") == "PipeWire:Interface:Node" and node_props(o).get("node.name") == name:
            return int(o["id"])
    return None


def node_rate(node_id: int, dump: list[dict] | None = None) -> float | None:
    """Current graph rate of a running node, if PipeWire reports it."""
    for o in dump if dump is not None else pw_dump():
        if o.get("id") == node_id:
            for fmt in ((o.get("info") or {}).get("params") or {}).get("Format") or []:
                rate = fmt.get("rate")
                if rate:
                    return float(rate)
    return None


def _set_pdeathsig() -> None:  # pragma: no cover - runs in the child
    try:
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        libc.prctl(1, signal.SIGTERM)  # PR_SET_PDEATHSIG: die with the app
    except OSError:
        pass


def _format_value(v: float) -> str:
    return repr(float(v))


def set_param_command(node_id: int, params: dict[str, float]) -> str:
    body = " ".join(f'"{k}" {_format_value(v)}' for k, v in params.items())
    return f"set-param {node_id} Props {{ params = [ {body} ] }}"


class PwCli:
    """A long-lived interactive `pw-cli`; commands are written to its stdin (~µs per update).

    Commands sent before pw-cli has enumerated the registry are silently dropped, so we wait for
    it to settle. Its stdout is very chatty; a reader thread drains it so the pipe never blocks.
    """

    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None
        self._ready = threading.Event()
        self._lock = threading.Lock()

    def _drain(self, proc: subprocess.Popen, ready: threading.Event) -> None:
        # Ready = prompt seen and then ~60 ms of silence: pw-cli prints its prompt before the
        # registry has been enumerated, and a set-param on a not-yet-known id is dropped.
        tail = b""
        fd = proc.stdout.fileno()
        prompted = False
        while True:
            try:
                readable, _, _ = select.select([fd], [], [], 0.06)
                if not readable:
                    if prompted:
                        ready.set()
                    continue
                chunk = os.read(fd, 65536)
            except OSError:
                break
            if not chunk:
                break
            if not prompted:
                tail = (tail + chunk)[-64:]
                prompted = b">>" in tail
        ready.set()  # never leave senders waiting on a dead process

    def _ensure(self) -> subprocess.Popen:
        if self._proc is None or self._proc.poll() is not None:
            self._ready = threading.Event()
            self._proc = subprocess.Popen(
                ["pw-cli"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=False,
                preexec_fn=_set_pdeathsig,
            )
            threading.Thread(target=self._drain, args=(self._proc, self._ready), daemon=True).start()
        self._ready.wait(3.0)
        return self._proc

    def send(self, line: str) -> None:
        with self._lock:
            for attempt in (0, 1):
                proc = self._ensure()
                try:
                    proc.stdin.write((line + "\n").encode())
                    proc.stdin.flush()
                    return
                except (BrokenPipeError, OSError):
                    self._proc = None
                    if attempt:
                        raise

    def close(self) -> None:
        with self._lock:
            if self._proc and self._proc.poll() is None:
                try:
                    self._proc.stdin.write(b"quit\n")
                    self._proc.stdin.flush()
                    self._proc.wait(2)
                except (OSError, subprocess.TimeoutExpired):
                    self._proc.kill()
            self._proc = None


class ChainProcess:
    """Runs `pipewire -c chain.conf` and tracks the sink/output node ids."""

    def __init__(self, conf_path: Path, sink_name: str, output_name: str) -> None:
        self.conf_path = Path(conf_path)
        self.sink_name = sink_name
        self.output_name = output_name
        self.proc: subprocess.Popen | None = None
        self.sink_id: int | None = None
        self.output_id: int | None = None
        self.log_path = self.conf_path.with_suffix(".log")

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None and self.sink_id is not None

    def start(self, config_text: str, timeout: float = 5.0) -> None:
        self.stop()
        self.conf_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.conf_path.with_suffix(".conf.tmp")
        tmp.write_text(config_text)
        tmp.replace(self.conf_path)
        log = open(self.log_path, "w")
        self.proc = subprocess.Popen(
            ["pipewire", "-c", str(self.conf_path)],
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            preexec_fn=_set_pdeathsig,
        )
        log.close()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise PipeWireError(f"filter-chain exited ({self.proc.returncode}): {self._tail_log()}")
            dump = pw_dump()
            sink = find_node(self.sink_name, dump)
            out = find_node(self.output_name, dump)
            if sink is not None and out is not None:
                self.sink_id, self.output_id = sink, out
                return
            time.sleep(0.05)
        self.stop()
        raise PipeWireError("filter-chain node did not appear in time")

    def _tail_log(self) -> str:
        try:
            return self.log_path.read_text()[-500:].strip()
        except OSError:
            return ""

    def stop(self) -> None:
        if self.proc is not None:
            if self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(3)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
                    self.proc.wait()
        self.proc = None
        self.sink_id = self.output_id = None


def run(cmd: list[str], timeout: float = 5.0) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def systemctl_user(*args: str) -> subprocess.CompletedProcess:
    return run(["systemctl", "--user", *args], timeout=15)

