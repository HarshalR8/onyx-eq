"""QObject exposing EQ state and actions to QML. QML never does audio maths; it asks here."""
from __future__ import annotations

import json
import os
import threading
from dataclasses import replace
from pathlib import Path

import numpy as np
from PySide6.QtCore import Property, QObject, QTimer, QUrl, Signal, Slot

from ..core import apo, graphic
from ..core.biquad import DEFAULT_RATE, auto_preamp, log_frequencies, magnitude_db
from ..core.models import (
    Band,
    BandType,
    EqMode,
    EqState,
    MAX_FREQ,
    MAX_Q,
    MIN_FREQ,
    MIN_Q,
    Preset,
    clamp,
)
from ..core.presets import PresetStore, Settings
from ..engine.chain_config import SINK_NAME
from .band_model import BandModel

CURVE_N = 400
HISTORY_LIMIT = 200
FLAT = "Flat"


def _url_to_path(url: str | QUrl) -> Path:
    q = url if isinstance(url, QUrl) else QUrl(url)
    return Path(q.toLocalFile() if q.isLocalFile() else str(url))


class Bridge(QObject):
    stateChanged = Signal()          # bands / preamp / mode (anything that alters the curve)
    selectedChanged = Signal()
    curveChanged = Signal()
    bypassChanged = Signal()
    rangeChanged = Signal()
    presetsChanged = Signal()
    presetChanged = Signal()
    outputsChanged = Signal()
    statusChanged = Signal()
    historyChanged = Signal()
    abChanged = Signal()
    optionsChanged = Signal()
    toast = Signal(str, str)         # (level, message)
    curveMorph = Signal()            # next curve change should animate (preset switch)

    _engineStatus = Signal(str, str)  # from the engine thread
    _devicesPolled = Signal(list, str)

    def __init__(self, engine=None, settings: Settings | None = None, store: PresetStore | None = None, parent=None):
        super().__init__(parent)
        self.engine = engine
        self.settings = settings or Settings()
        self.store = store or PresetStore()
        self.model = BandModel(self)

        self._state = self.settings.last_state() or EqState()
        self._selected = 0 if self._state.bands else -1
        self._solo = -1
        self._bypass = False
        self._range = int(self.settings.get("range", 12))
        self._graphic_count = int(self.settings.get("graphic_count", 31))
        self._preset = self.settings.get("preset", FLAT)
        self._saved_state = self._state
        self._history: list[EqState] = []
        self._future: list[EqState] = []
        self._edit_base: EqState | None = None
        self._ab = {"A": self._state, "B": None}
        self._ab_slot = "A"
        self._status_level, self._status = "ok", ""
        self._outputs: list[dict] = []
        self._output = self.settings.get("output")
        self._live_output: str | None = None  # last system default seen by the device poll
        self._follow_default = True

        self._freqs = log_frequencies(CURVE_N)
        self._cache: dict[Band, np.ndarray] = {}
        self._cache_rate = DEFAULT_RATE
        self._curve: list[float] = []
        self._band_curve: list[float] = []
        self._max_level = 0.0
        self._dirty_curve = True
        self._dirty_engine = False
        self._tick = QTimer(self, interval=16)  # ~60 Hz coalescing of curve + engine updates
        self._tick.timeout.connect(self._flush)
        self._tick.start()

        self._engineStatus.connect(self._on_engine_status)
        self._devicesPolled.connect(self._on_devices)
        self._poll = QTimer(self, interval=2000)
        self._poll.timeout.connect(self._poll_devices)
        self.model.sync(self._state.bands)
        self._recompute_curve()

    # ---- lifecycle --------------------------------------------------------------------------
    def engine_status_callback(self, level: str, msg: str) -> None:
        self._engineStatus.emit(level, msg)

    def start_engine(self) -> None:
        if not self.engine:
            self._set_status("ok", "Audio engine disabled")
            return
        # Normally the EQ follows the system default device. ONYX_EQ_NO_DEFAULT=1 (for development)
        # leaves the default alone and equalizes the saved output instead.
        self._follow_default = os.environ.get("ONYX_EQ_NO_DEFAULT") != "1"
        try:
            self.engine.start(
                self._effective_state(),
                self._bypass,
                output=None if self._follow_default else self._output,
                make_default=self._follow_default,
                fallback_default=self.settings.get("output"),
            )
        except Exception as e:
            self._set_status("error", str(e))
            return
        self._output = self.engine.output
        self._poll_devices()
        self._poll.start()

    def shutdown(self) -> None:
        self._tick.stop()
        self._poll.stop()
        self.settings.data.update(
            last_state=self._state.to_dict(),
            range=self._range,
            graphic_count=self._graphic_count,
            preset=self._preset,
            output=self._output,
        )
        self.settings.data.pop("previous_default", None)  # from versions that took over the default
        self.settings.save()
        if self.engine:
            self.engine.shutdown(keep_running=bool(self.settings.get("keep_running", False)))

    # ---- state plumbing ---------------------------------------------------------------------
    def _effective_state(self) -> EqState:
        if 0 <= self._solo < len(self._state.bands):
            bands = tuple(replace(b, enabled=(i == self._solo)) for i, b in enumerate(self._state.bands))
            return replace(self._state, bands=bands)
        return self._state

    def _set_state(self, state: EqState, record: bool = True, morph: bool = False) -> None:
        if state == self._state:
            return
        if record and self._edit_base is None:
            self._push_history(self._state)
        self._state = state
        if self._solo >= len(state.bands):
            self._solo = -1
        if self._selected >= len(state.bands):
            self._selected = len(state.bands) - 1
            self.selectedChanged.emit()
        self.model.sync(state.bands)
        self._ab[self._ab_slot] = state
        if morph:
            self.curveMorph.emit()
        self._dirty_curve = self._dirty_engine = True
        self.stateChanged.emit()
        self.presetChanged.emit()  # dirty flag

    def _push_history(self, state: EqState) -> None:
        self._history.append(state)
        del self._history[:-HISTORY_LIMIT]
        self._future.clear()
        self.historyChanged.emit()

    def _flush(self) -> None:
        if self._dirty_curve:
            self._recompute_curve()
        if self._dirty_engine and self.engine:
            self.engine.submit(self._effective_state(), self._bypass)
        self._dirty_curve = self._dirty_engine = False

    def _rate(self) -> float:
        return getattr(self.engine, "rate", DEFAULT_RATE) if self.engine else DEFAULT_RATE

    def _band_db(self, band: Band, rate: float) -> np.ndarray:
        """Per-band response, cached: a drag or slider move only recomputes the band it changes."""
        if rate != self._cache_rate or len(self._cache) > 4096:
            self._cache, self._cache_rate = {}, rate
        db = self._cache.get(band)
        if db is None:
            db = self._cache[band] = magnitude_db(band, self._freqs, rate)
        return db

    def _recompute_curve(self) -> None:
        st = self._effective_state()
        rate = self._rate()
        total = np.full(len(self._freqs), st.preamp)
        for band in st.bands:
            if band.enabled:
                total += self._band_db(band, rate)
        self._curve = total.tolist()
        self._max_level = float(np.max(total))
        if 0 <= self._selected < len(st.bands):
            self._band_curve = self._band_db(replace(st.bands[self._selected], enabled=True), rate).tolist()
        else:
            self._band_curve = []
        self._dirty_curve = False
        self.curveChanged.emit()

    # ---- read-only properties ---------------------------------------------------------------
    bandModel = Property(QObject, lambda self: self.model, constant=True)
    curve = Property(list, lambda self: self._curve, notify=curveChanged)
    bandCurve = Property(list, lambda self: self._band_curve, notify=curveChanged)
    maxLevel = Property(float, lambda self: self._max_level, notify=curveChanged)
    clipping = Property(bool, lambda self: self._max_level > 0.05 and not self._bypass, notify=curveChanged)
    curveMinHz = Property(float, lambda self: float(self._freqs[0]), constant=True)
    curveMaxHz = Property(float, lambda self: float(self._freqs[-1]), constant=True)
    bandCount = Property(int, lambda self: len(self._state.bands), notify=stateChanged)
    preamp = Property(float, lambda self: self._state.preamp, notify=stateChanged)
    mode = Property(str, lambda self: self._state.mode.value, notify=stateChanged)
    graphicCount = Property(int, lambda self: self._graphic_count, notify=stateChanged)
    graphicPresets = Property(list, lambda self: list(graphic.PRESET_COUNTS), constant=True)
    bandTypes = Property(list, lambda self: [{"value": t.value, "name": t.display_name} for t in BandType], constant=True)
    solo = Property(int, lambda self: self._solo, notify=stateChanged)
    statusLevel = Property(str, lambda self: self._status_level, notify=statusChanged)
    status = Property(str, lambda self: self._status, notify=statusChanged)
    canUndo = Property(bool, lambda self: bool(self._history), notify=historyChanged)
    canRedo = Property(bool, lambda self: bool(self._future), notify=historyChanged)
    abSlot = Property(str, lambda self: self._ab_slot, notify=abChanged)
    presets = Property(list, lambda self: [FLAT] + [n for n in self.store.names() if n != FLAT], notify=presetsChanged)
    presetName = Property(str, lambda self: self._preset, notify=presetChanged)
    presetDirty = Property(bool, lambda self: self._state != self._saved_state, notify=presetChanged)
    outputs = Property(list, lambda self: self._outputs, notify=outputsChanged)
    output = Property(str, lambda self: self._output or "", notify=outputsChanged)
    engineEnabled = Property(bool, lambda self: self.engine is not None, constant=True)

    def _get_selected(self) -> int:
        return self._selected

    def _set_selected(self, i: int) -> None:
        i = int(i) if -1 <= int(i) < len(self._state.bands) else -1
        if i != self._selected:
            self._selected = i
            self.selectedChanged.emit()
            self._dirty_curve = True

    selected = Property(int, _get_selected, _set_selected, notify=selectedChanged)

    def _get_bypass(self) -> bool:
        return self._bypass

    def _set_bypass(self, on: bool) -> None:
        if bool(on) != self._bypass:
            self._bypass = bool(on)
            self._dirty_engine = self._dirty_curve = True
            self.bypassChanged.emit()

    bypass = Property(bool, _get_bypass, _set_bypass, notify=bypassChanged)

    def _get_range(self) -> int:
        return self._range

    def _set_range(self, r: int) -> None:
        if int(r) != self._range:
            self._range = int(r)
            self.rangeChanged.emit()

    rangeDb = Property(int, _get_range, _set_range, notify=rangeChanged)

    def _opt(name, default, notify):
        def get(self):
            return bool(self.settings.get(name, default))

        def set_(self, v):
            if bool(v) != get(self):
                self.settings.set(name, bool(v))
                self.optionsChanged.emit()
                if name == "keep_running" and not v:
                    from ..engine import service

                    try:
                        service.uninstall()
                    except OSError:
                        pass

        return Property(bool, get, set_, notify=notify)

    keepRunning = _opt("keep_running", False, optionsChanged)
    autoSwitch = _opt("auto_switch", True, optionsChanged)
    del _opt

    @Property(bool, notify=optionsChanged)
    def keepRunningAvailable(self) -> bool:
        from ..engine import service

        return self.engine is not None and service.available()

    @Property(str, notify=outputsChanged)
    def outputPreset(self) -> str:
        return (self.settings.get("device_presets") or {}).get(self._output or "", "")

    # ---- band editing -----------------------------------------------------------------------
    def _band(self, i: int) -> Band | None:
        return self._state.bands[i] if 0 <= i < len(self._state.bands) else None

    @Slot(int, result="QVariant")
    def bandAt(self, i: int) -> dict:
        b = self._band(i)
        if b is None:
            return {}
        return {"freq": b.freq, "gain": b.gain, "q": b.q, "enabled": b.enabled, "hasGain": b.type.has_gain, "type": b.type.value}

    @Slot(int, result=str)
    def bandTypeAt(self, i: int) -> str:
        b = self._band(i)
        return b.type.value if b else ""

    @Slot(int, result=bool)
    def bandEnabledAt(self, i: int) -> bool:
        b = self._band(i)
        return bool(b and b.enabled)

    def _edit(self, i: int, **changes) -> None:
        b = self._band(i)
        if b is not None:
            self._set_state(self._state.with_band(i, replace(b, **changes)))

    @Slot()
    def beginEdit(self) -> None:
        """Group the following changes (a drag) into one undo step."""
        if self._edit_base is None:
            self._edit_base = self._state

    @Slot()
    def endEdit(self) -> None:
        base, self._edit_base = self._edit_base, None
        if base is not None and base != self._state:
            self._push_history(base)

    @Slot(int, float, float)
    def moveBand(self, i: int, freq: float, gain: float) -> None:
        b = self._band(i)
        if b is not None:
            self._edit(i, freq=freq, gain=gain if b.type.has_gain else b.gain)

    @Slot(int, float)
    def setBandFreq(self, i: int, v: float) -> None:
        self._edit(i, freq=v)

    @Slot(int, float)
    def setBandGain(self, i: int, v: float) -> None:
        self._edit(i, gain=v)

    @Slot(int, float)
    def setBandQ(self, i: int, v: float) -> None:
        self._edit(i, q=v)

    @Slot(int, float)
    def scaleQ(self, i: int, factor: float) -> None:
        b = self._band(i)
        if b is not None:
            self._edit(i, q=round(clamp(b.q * factor, MIN_Q, MAX_Q), 3))

    @Slot(int, str)
    def setBandType(self, i: int, t: str) -> None:
        self._edit(i, type=BandType(t))

    @Slot(int, bool)
    def setBandEnabled(self, i: int, on: bool) -> None:
        self._edit(i, enabled=bool(on))

    @Slot(int)
    def resetGain(self, i: int) -> None:
        self._edit(i, gain=0.0)

    @Slot(int, float)
    def nudgeFreq(self, i: int, octaves: float) -> None:
        b = self._band(i)
        if b is not None:
            self._edit(i, freq=clamp(b.freq * 2.0 ** octaves, MIN_FREQ, MAX_FREQ))

    @Slot(int, float)
    def nudgeGain(self, i: int, db: float) -> None:
        b = self._band(i)
        if b is not None and b.type.has_gain:
            self._edit(i, gain=round(b.gain + db, 2))

    @Slot(float, float, result=int)
    def addBand(self, freq: float, gain: float) -> int:
        if self._state.mode is EqMode.GRAPHIC:
            return -1
        self._set_state(self._state.add_band(Band(BandType.PEAKING, freq, gain, 1.0)))
        self.selected = len(self._state.bands) - 1
        return self._selected

    @Slot(int)
    def removeBand(self, i: int) -> None:
        if self._band(i) is None or self._state.mode is EqMode.GRAPHIC:
            return
        if self._solo == i:
            self._solo = -1
        elif self._solo > i:
            self._solo -= 1
        self._set_state(self._state.remove_band(i))
        self.selected = min(i, len(self._state.bands) - 1)

    @Slot(int)
    def toggleSolo(self, i: int) -> None:
        self._solo = -1 if self._solo == i else i
        self._dirty_curve = self._dirty_engine = True
        self.stateChanged.emit()

    @Slot(float)
    def setPreamp(self, db: float) -> None:
        self._set_state(replace(self._state, preamp=round(clamp(db, -30.0, 30.0), 2)))

    @Slot()
    def autoPreamp(self) -> None:
        self.setPreamp(auto_preamp(self._state.bands, self._rate()))

    @Slot(int, result=list)
    def graphicLabels(self, n: int) -> list:
        # also evaluated while the graphic view is hidden, e.g. with zero parametric bands
        return [_fmt_hz(f) for f in graphic.layout(n)] if n >= 1 else []

    # ---- modes ------------------------------------------------------------------------------
    @Slot(str)
    def setMode(self, mode: str) -> None:
        mode = EqMode(mode)
        if mode is self._state.mode:
            return
        if mode is EqMode.GRAPHIC:
            bands = graphic.from_parametric(self._state.bands, self._graphic_count, self._rate())
        else:
            bands = tuple(b for b in self._state.bands if abs(b.gain) >= 0.05)
        self._solo = -1
        self._set_state(replace(self._state, bands=bands, mode=mode), morph=True)
        self.selected = 0 if bands and mode is EqMode.PARAMETRIC else -1

    @Slot(int)
    def setGraphicCount(self, n: int) -> None:
        n = int(clamp(n, 2, 511))
        if n == self._graphic_count and self._state.mode is EqMode.GRAPHIC and len(self._state.bands) == n:
            return
        self._graphic_count = n
        if self._state.mode is EqMode.GRAPHIC:
            bands = graphic.from_parametric(self._state.bands, n, self._rate())
            self._set_state(replace(self._state, bands=bands), morph=True)
        self.stateChanged.emit()

    @Slot(int, float)
    def setGraphicGain(self, i: int, g: float) -> None:
        self._edit(i, gain=round(g, 1))

    @Slot()
    def flattenGraphic(self) -> None:
        bands = tuple(replace(b, gain=0.0) for b in self._state.bands)
        self._set_state(replace(self._state, bands=bands), morph=True)

    # ---- history / A-B ----------------------------------------------------------------------
    @Slot()
    def undo(self) -> None:
        if self._history:
            self._future.append(self._state)
            prev = self._history.pop()
            self._set_state(prev, record=False, morph=True)
            self.historyChanged.emit()

    @Slot()
    def redo(self) -> None:
        if self._future:
            self._history.append(self._state)
            nxt = self._future.pop()
            self._set_state(nxt, record=False, morph=True)
            self.historyChanged.emit()

    @Slot()
    def toggleAB(self) -> None:
        other = "B" if self._ab_slot == "A" else "A"
        if self._ab[other] is None:
            self._ab[other] = self._state  # first switch: B starts as a copy of A
        self._ab_slot = other
        self._set_state(self._ab[other], record=False, morph=True)
        self.abChanged.emit()

    @Slot()
    def copyToOther(self) -> None:
        other = "B" if self._ab_slot == "A" else "A"
        self._ab[other] = self._state
        self.toast.emit("ok", f"Copied {self._ab_slot} to {other}")

    # ---- presets ----------------------------------------------------------------------------
    def _load_state(self, state: EqState, name: str) -> None:
        self._solo = -1
        if state.mode is EqMode.GRAPHIC:
            self._graphic_count = len(state.bands)
        self._preset = name
        self._saved_state = state
        self._set_state(state, morph=True)
        self.selected = 0 if state.bands and state.mode is EqMode.PARAMETRIC else -1
        self.presetChanged.emit()

    @Slot(str)
    def loadPreset(self, name: str) -> None:
        if name == FLAT and not self.store.exists(FLAT):
            mode = self._state.mode
            bands = graphic.bands_for(self._graphic_count) if mode is EqMode.GRAPHIC else ()
            self._load_state(EqState(bands, 0.0, mode), FLAT)
            return
        try:
            self._load_state(self.store.load(name).state, name)
        except (OSError, ValueError, KeyError) as e:
            self.toast.emit("error", f"Couldn't load “{name}”: {e}")

    @Slot(str, result=bool)
    def savePreset(self, name: str) -> bool:
        name = name.strip() or self._preset
        if not name:
            return False
        try:
            self.store.save(Preset(name, self._state))
        except OSError as e:
            self.toast.emit("error", f"Couldn't save: {e}")
            return False
        self._preset, self._saved_state = name, self._state
        self.presetsChanged.emit()
        self.presetChanged.emit()
        self.toast.emit("ok", f"Saved “{name}”")
        return True

    @Slot(str, str, result=bool)
    def renamePreset(self, old: str, new: str) -> bool:
        new = new.strip()
        if not new or old == FLAT:
            return False
        try:
            self.store.rename(old, new)
        except FileExistsError:
            self.toast.emit("error", f"“{new}” already exists")
            return False
        except OSError as e:
            self.toast.emit("error", str(e))
            return False
        dp = self.settings.get("device_presets") or {}
        self.settings.set("device_presets", {k: (new if v == old else v) for k, v in dp.items()})
        if self._preset == old:
            self._preset = new
        self.presetsChanged.emit()
        self.presetChanged.emit()
        return True

    @Slot(str)
    def deletePreset(self, name: str) -> None:
        self.store.delete(name)
        if self._preset == name:
            self._preset = ""
        self.presetsChanged.emit()
        self.presetChanged.emit()

    @Slot(str, result=bool)
    def hasPreset(self, name: str) -> bool:
        return name == FLAT or self.store.exists(name)

    @Slot("QVariant")
    def importFile(self, url) -> None:
        path = _url_to_path(url.toString() if isinstance(url, QUrl) else str(url))
        try:
            text = path.read_text(errors="replace")
        except OSError as e:
            self.toast.emit("error", f"Couldn't read {path.name}: {e}")
            return
        name = path.stem
        if path.suffix.lower() == ".json":
            try:
                p = Preset.from_dict(json.loads(text))
                state, name, warnings = p.state, p.name, []
            except (ValueError, KeyError) as e:
                self.toast.emit("error", f"Not an Onyx EQ preset: {e}")
                return
        else:
            # GraphicEQ curves are fitted with 127 bands; fewer can't follow AutoEQ's detail
            result = apo.parse(text, graphic_bands=max(self._graphic_count, 127), rate=self._rate())
            state, warnings = result.state, result.warnings
            if not state.bands and not state.preamp:
                self.toast.emit("error", f"No filters found in {path.name}")
                return
        for suffix in (" ParametricEQ", " GraphicEQ", " FixedBandEQ"):
            name = name.removesuffix(suffix)
        self._load_state(state, name)
        self._saved_state = EqState()  # imported, not saved yet
        self.presetChanged.emit()
        msg = f"Imported {path.name}: {len(state.bands)} bands"
        if warnings:
            msg += f" ({len(warnings)} lines skipped: {warnings[0]}{'…' if len(warnings) > 1 else ''})"
        self.toast.emit("warn" if warnings else "ok", msg)

    @Slot("QVariant", str)
    def exportFile(self, url, kind: str) -> None:
        path = _url_to_path(url.toString() if isinstance(url, QUrl) else str(url))
        if kind == "json":
            text = json.dumps(Preset(self._preset or path.stem, self._state).to_dict(), indent=2)
        elif kind == "graphic":
            text = apo.export_graphic(self._state, rate=self._rate())
        else:
            text = apo.export_parametric(self._state)
        try:
            path.write_text(text)
        except OSError as e:
            self.toast.emit("error", f"Couldn't write {path.name}: {e}")
            return
        self.toast.emit("ok", f"Exported {path.name}")

    # ---- outputs ----------------------------------------------------------------------------
    def _poll_devices(self) -> None:
        if not self.engine:
            return

        def work():
            from ..engine import devices, pipewire as pw

            try:
                dump = pw.pw_dump()
                sinks = [{"name": s.name, "description": s.description} for s in devices.list_sinks(dump)]
                default = devices.default_sink_name(dump)
                if default == SINK_NAME:  # e.g. picked in the desktop's sound menu
                    self.engine.repair_default()
                    default = self.engine.output
            except Exception:
                return
            self._devicesPolled.emit(sinks, default or "")

        threading.Thread(target=work, daemon=True).start()

    def _on_devices(self, sinks: list, default: str) -> None:
        if sinks != self._outputs:
            self._outputs = sinks
            self.outputsChanged.emit()
        # follow the system default device (headphones plugged in, picked in the sound menu, …)
        if not self._follow_default or not default or default == self._live_output:
            return
        first = self._live_output is None
        self._live_output = default
        if default != self._output:
            self._output = default
            self.engine.set_output(default)
            self.outputsChanged.emit()
        if not first:
            self._apply_device_preset()

    @Slot(str)
    def setOutput(self, name: str) -> None:
        if not name or name == self._output:
            return
        self._output = name
        self._live_output = name
        if self.engine:
            self.engine.set_output(name)
        self.outputsChanged.emit()
        self._apply_device_preset()

    def _apply_device_preset(self) -> None:
        if not self.autoSwitch:
            return
        name = (self.settings.get("device_presets") or {}).get(self._output or "")
        if name and name != self._preset and self.hasPreset(name):
            self.loadPreset(name)
            self.toast.emit("ok", f"Loaded “{name}” for this output")

    @Slot(bool)
    def bindPresetToOutput(self, on: bool) -> None:
        dp = dict(self.settings.get("device_presets") or {})
        if on and self._preset:
            dp[self._output or ""] = self._preset
        else:
            dp.pop(self._output or "", None)
        self.settings.set("device_presets", dp)
        self.outputsChanged.emit()

    # ---- misc -------------------------------------------------------------------------------
    def _set_status(self, level: str, msg: str) -> None:
        if (level, msg) != (self._status_level, self._status):
            self._status_level, self._status = level, msg
            self.statusChanged.emit()

    def _on_engine_status(self, level: str, msg: str) -> None:
        self._set_status(level, msg)
        if level == "error":
            self.toast.emit("error", msg)
        elif level == "ok" and self.engine and getattr(self.engine, "rate", None):
            self._dirty_curve = True

    @Slot(float, result=str)
    def formatHz(self, f: float) -> str:
        return _fmt_hz(f)


def _fmt_hz(f: float) -> str:
    """20 -> '20', 31.5 -> '31.5', 1250 -> '1.25k', 16000 -> '16k'."""
    if f >= 10000:
        return f"{f / 1000:.0f}k"
    if f >= 1000:
        return f"{f / 1000:.2f}".rstrip("0").rstrip(".") + "k"
    if f >= 100:
        return f"{f:.0f}"
    return f"{f:.1f}".rstrip("0").rstrip(".")
