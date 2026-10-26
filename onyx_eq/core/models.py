"""Plain data model for an equalizer. No Qt, no I/O."""
from __future__ import annotations

from dataclasses import dataclass, field, replace, asdict
from enum import Enum


class BandType(str, Enum):
    PEAKING = "peaking"
    LOW_SHELF = "lowshelf"
    HIGH_SHELF = "highshelf"
    LOW_PASS = "lowpass"
    HIGH_PASS = "highpass"
    NOTCH = "notch"
    BAND_PASS = "bandpass"
    ALL_PASS = "allpass"

    @property
    def pw_label(self) -> str:
        """Name of the PipeWire filter-chain builtin."""
        return "bq_" + self.value

    @property
    def has_gain(self) -> bool:
        return self in (BandType.PEAKING, BandType.LOW_SHELF, BandType.HIGH_SHELF)

    @property
    def display_name(self) -> str:
        return _DISPLAY[self]


_DISPLAY = {
    BandType.PEAKING: "Peak",
    BandType.LOW_SHELF: "Low Shelf",
    BandType.HIGH_SHELF: "High Shelf",
    BandType.LOW_PASS: "Low Pass",
    BandType.HIGH_PASS: "High Pass",
    BandType.NOTCH: "Notch",
    BandType.BAND_PASS: "Band Pass",
    BandType.ALL_PASS: "All Pass",
}

MIN_FREQ = 10.0
MAX_FREQ = 22000.0
MIN_Q = 0.05
MAX_Q = 30.0
MIN_GAIN = -30.0
MAX_GAIN = 30.0
DEFAULT_Q = 0.7071067811865476


def clamp(value: float, lo: float, hi: float) -> float:
    return lo if value < lo else hi if value > hi else value


@dataclass(frozen=True, slots=True)
class Band:
    type: BandType = BandType.PEAKING
    freq: float = 1000.0
    gain: float = 0.0
    q: float = DEFAULT_Q
    enabled: bool = True

    def clamped(self) -> "Band":
        return replace(
            self,
            freq=clamp(float(self.freq), MIN_FREQ, MAX_FREQ),
            gain=clamp(float(self.gain), MIN_GAIN, MAX_GAIN),
            q=clamp(float(self.q), MIN_Q, MAX_Q),
        )

    def to_dict(self) -> dict:
        d = asdict(self)
        d["type"] = self.type.value
        return d

    @staticmethod
    def from_dict(d: dict) -> "Band":
        return Band(
            type=BandType(d.get("type", "peaking")),
            freq=float(d.get("freq", 1000.0)),
            gain=float(d.get("gain", 0.0)),
            q=float(d.get("q", DEFAULT_Q)),
            enabled=bool(d.get("enabled", True)),
        ).clamped()


class EqMode(str, Enum):
    PARAMETRIC = "parametric"
    GRAPHIC = "graphic"


@dataclass(frozen=True, slots=True)
class EqState:
    bands: tuple[Band, ...] = ()
    preamp: float = 0.0
    mode: EqMode = EqMode.PARAMETRIC

    def with_band(self, index: int, band: Band) -> "EqState":
        bands = list(self.bands)
        bands[index] = band.clamped()
        return replace(self, bands=tuple(bands))

    def add_band(self, band: Band) -> "EqState":
        return replace(self, bands=self.bands + (band.clamped(),))

    def remove_band(self, index: int) -> "EqState":
        return replace(self, bands=self.bands[:index] + self.bands[index + 1:])

    def to_dict(self) -> dict:
        return {
            "preamp": self.preamp,
            "mode": self.mode.value,
            "bands": [b.to_dict() for b in self.bands],
        }

    @staticmethod
    def from_dict(d: dict) -> "EqState":
        return EqState(
            bands=tuple(Band.from_dict(b) for b in d.get("bands", [])),
            preamp=float(d.get("preamp", 0.0)),
            mode=EqMode(d.get("mode", "parametric")),
        )


@dataclass(frozen=True, slots=True)
class Preset:
    name: str
    state: EqState = field(default_factory=EqState)

    def to_dict(self) -> dict:
        return {"name": self.name, "version": 1, **self.state.to_dict()}

    @staticmethod
    def from_dict(d: dict) -> "Preset":
        return Preset(name=str(d.get("name", "Untitled")), state=EqState.from_dict(d))
