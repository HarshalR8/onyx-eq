"""Keeps the running filter-chain in sync with an EqState.

`submit()` never blocks: a worker thread takes the latest submitted state (coalescing anything in
between) and either sends live `set-param` updates or, when the slot layout can't hold the new
bands, rebuilds the chain.

The chain is a WirePlumber smart filter targeting the output device (see chain_config). The device
stays the system default, so the desktop's volume slider still controls the hardware.
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

from ..core.biquad import DEFAULT_RATE
from ..core.models import EqState
from ..core.presets import config_dir
from . import devices, pipewire as pw, service
from .chain_config import OUTPUT_NAME, SINK_NAME, Layout, assign_slots, build_config, params_for, plan_layout

StatusFn = Callable[[str, str], None]  # (level: "ok"|"busy"|"error", message)


class EngineController:
    def __init__(self, conf_dir: Path | None = None, on_status: StatusFn | None = None):
        self.dir = Path(conf_dir) if conf_dir else config_dir()
        self.chain = pw.ChainProcess(self.dir / "chain.conf", SINK_NAME, OUTPUT_NAME)
        self.cli = pw.PwCli()
        self.on_status = on_status or (lambda level, msg: None)
        self.layout: Layout = ()
        self.sent: dict[str, float] = {}
        self.rate = DEFAULT_RATE
        self.output: str | None = None
        self.make_default = True  # picking an output also makes it the system default

        self._desired: tuple[EqState, bool] | None = None
        self._lock = threading.Lock()
        self._wake = threading.Event()
        self._stop = False
        self._idle = threading.Event()
        self._idle.set()
        self._thread = threading.Thread(target=self._loop, name="onyx-engine", daemon=True)
        self._thread.start()
        self.reloads = 0

    # ---- public API -------------------------------------------------------------------------
    def submit(self, state: EqState, bypass: bool = False) -> None:
        with self._lock:
            self._desired = (state, bypass)
            self._idle.clear()
        self._wake.set()

    def wait_idle(self, timeout: float | None = None) -> bool:
        return self._idle.wait(timeout)

    def start(
        self,
        state: EqState,
        bypass: bool = False,
        output: str | None = None,
        make_default: bool = True,
        fallback_default: str | None = None,
    ) -> None:
        """Pick the device to equalize, then build the chain (asynchronously).

        By default that's the current system default device. `output` forces a specific one.
        `fallback_default` is used when the default is still Onyx EQ itself, which older versions
        set (WirePlumber remembers it), so the real device becomes the default again.
        """
        pw.require_tools()
        if service.is_active():
            service.stop()
        dump = pw.pw_dump()
        hw = [s.name for s in devices.list_sinks(dump)]
        current = devices.default_sink_name(dump)
        if current not in hw:
            current = fallback_default if fallback_default in hw else (hw[0] if hw else None)
        self.output = output if output in hw else current
        self.make_default = make_default
        if current and SINK_NAME in (devices.default_sink_name(dump), devices.configured_default_sink_name(dump)):
            devices.set_default_sink(current, dump)
        elif make_default and output in hw and output != devices.default_sink_name(dump):
            devices.set_default_sink(output, dump)
        self.layout = ()  # force a build
        self.submit(state, bypass)

    def set_output(self, sink_name: str) -> None:
        """Equalize another device (and make it the default unless make_default is off)."""
        self.output = sink_name
        if self.make_default and devices.default_sink_name() != sink_name:
            devices.set_default_sink(sink_name)
        if self.chain.running and self.chain.sink_id is not None:
            if devices.set_filter_target(self.chain.sink_id, sink_name):
                self.on_status("ok", "")
                return
        self.layout = ()  # fall back to a rebuild with the new target
        if self._desired:
            self.submit(*self._desired)

    def repair_default(self) -> None:
        """Something made Onyx EQ itself the default; hand that back to the real device."""
        if self.output:
            devices.set_default_sink(self.output)

    def reload(self) -> None:
        self.layout = ()
        if self._desired:
            self.submit(*self._desired)

    def shutdown(self, keep_running: bool = False) -> None:
        """Stop the worker and the chain. With keep_running, hand the chain to the systemd unit."""
        self._stop = True
        self._wake.set()
        self._thread.join(3)
        self.cli.close()
        handoff = keep_running and bool(self.layout) and service.available()
        self._forget_filter_target()
        self.chain.stop()
        if handoff:
            # bake the live values into chain.conf so the service starts exactly where we are
            self.chain.conf_path.write_text(build_config(self.layout, self.sent, target=self.output))
            service.install(self.chain.conf_path)
            service.start()

    def _forget_filter_target(self) -> None:
        if self.chain.sink_id is not None:
            try:
                devices.clear_filter_target(self.chain.sink_id)
            except (pw.PipeWireError, OSError):
                pass

    # ---- worker -----------------------------------------------------------------------------
    def _loop(self) -> None:
        while True:
            self._wake.wait()
            if self._stop:
                return
            self._wake.clear()
            with self._lock:
                desired = self._desired
            if desired is not None:
                try:
                    self._apply(*desired)
                except Exception as e:  # report and keep the thread alive
                    self.on_status("error", str(e))
            with self._lock:
                if not self._wake.is_set():
                    self._idle.set()

    def _apply(self, state: EqState, bypass: bool) -> None:
        assignment = assign_slots(state.bands, self.layout) if self.layout else None
        if assignment is None or not self.chain.running:
            self._rebuild(state, bypass)
            return
        params = params_for(state, self.layout, assignment, bypass)
        changed = {k: v for k, v in params.items() if self.sent.get(k) != v}
        if changed:
            self.cli.send(pw.set_param_command(self.chain.sink_id, changed))
            self.sent.update(changed)

    def _rebuild(self, state: EqState, bypass: bool) -> None:
        self.on_status("busy", "Starting equalizer…")
        self.cli.close()  # a fresh pw-cli is sure to know the new node ids
        self._forget_filter_target()
        layout = plan_layout(state.bands)
        assignment = assign_slots(state.bands, layout)
        params = params_for(state, layout, assignment, bypass)
        self.chain.start(build_config(layout, params, target=self.output))
        self.layout, self.sent = layout, params
        self.reloads += 1
        devices.reset_volume(self.chain.sink_id)
        dump = pw.pw_dump()
        self.rate = pw.node_rate(self.chain.sink_id, dump) or self.rate
        self.on_status("ok", "")
