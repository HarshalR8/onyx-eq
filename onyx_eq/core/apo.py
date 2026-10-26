"""Equalizer APO / AutoEQ import and export.

Supported:
  Preamp: -6.2 dB
  Filter 1: ON PK Fc 105 Hz Gain 4.0 dB Q 0.70
  Filter: ON LSC Fc 105 Hz Gain 4.0 dB         (Q optional; BW Oct n also accepted)
  GraphicEQ: 20 -1.2; 21 -1.3; ...              (fitted to graphic-mode peaking bands)
  # and ; comments, blank lines
Anything else (Device:, Channel:, Include:, Delay:, Copy:, Stage:, Eval:, ...) is skipped and reported
as a warning.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

from . import graphic
from .biquad import DEFAULT_RATE, state_response_db
from .models import Band, BandType, DEFAULT_Q, EqMode, EqState

# APO filter code -> (band type, uses gain)
_TYPES: dict[str, BandType] = {
    "PK": BandType.PEAKING,
    "PEQ": BandType.PEAKING,
    "MODAL": BandType.PEAKING,
    "LS": BandType.LOW_SHELF,
    "LSC": BandType.LOW_SHELF,
    "HS": BandType.HIGH_SHELF,
    "HSC": BandType.HIGH_SHELF,
    "LP": BandType.LOW_PASS,
    "LPQ": BandType.LOW_PASS,
    "HP": BandType.HIGH_PASS,
    "HPQ": BandType.HIGH_PASS,
    "NO": BandType.NOTCH,
    "BP": BandType.BAND_PASS,
    "AP": BandType.ALL_PASS,
}
_EXPORT_CODE = {
    BandType.PEAKING: "PK",
    BandType.LOW_SHELF: "LSC",
    BandType.HIGH_SHELF: "HSC",
    BandType.LOW_PASS: "LPQ",
    BandType.HIGH_PASS: "HPQ",
    BandType.NOTCH: "NO",
    BandType.BAND_PASS: "BP",
    BandType.ALL_PASS: "AP",
}

_NUM = r"[-+]?(?:\d+(?:[.,]\d*)?|[.,]\d+)(?:[eE][-+]?\d+)?"
_FILTER_RE = re.compile(r"^filter\s*\d*\s*:\s*(?P<rest>.*)$", re.I)
_PREAMP_RE = re.compile(rf"^preamp\s*:\s*(?P<v>{_NUM})\s*(?:db)?\s*$", re.I)
_DIRECTIVE_RE = re.compile(r"^(?P<name>[A-Za-z][A-Za-z ]*?)\s*:")


@dataclass
class ParseResult:
    state: EqState
    warnings: list[str] = field(default_factory=list)


def _num(s: str) -> float:
    return float(s.replace(",", "."))


def _strip_comment(line: str) -> str:
    for marker in ("#",):
        i = line.find(marker)
        if i >= 0:
            line = line[:i]
    return line.strip()


def _parse_filter(rest: str) -> tuple[Band | None, str | None]:
    tokens = rest.split()
    if not tokens:
        return None, "empty filter"
    enabled = True
    if tokens[0].upper() in ("ON", "OFF"):
        enabled = tokens[0].upper() == "ON"
        tokens = tokens[1:]
    if not tokens:
        return None, "filter without type"
    code = tokens[0].upper()
    if code in ("NONE",):
        return None, None
    btype = _TYPES.get(code)
    if btype is None:
        return None, f"unsupported filter type '{tokens[0]}'"
    args = tokens[1:]
    freq = gain = q = bw = None
    i = 0
    while i < len(args):
        key = args[i].lower()
        try:
            if key == "fc" and i + 1 < len(args):
                freq = _num(args[i + 1])
                i += 2
                if i < len(args) and args[i].lower() == "hz":
                    i += 1
                continue
            if key == "gain" and i + 1 < len(args):
                gain = _num(args[i + 1])
                i += 2
                if i < len(args) and args[i].lower() == "db":
                    i += 1
                continue
            if key == "q" and i + 1 < len(args):
                q = _num(args[i + 1])
                i += 2
                continue
            if key == "bw" and i + 2 < len(args) and args[i + 1].lower() == "oct":
                bw = _num(args[i + 2])
                i += 3
                continue
        except ValueError:
            return None, f"bad number in '{rest}'"
        # shelf slope form, e.g. "LS 6dB Fc ..." — keep default Q
        i += 1
    if freq is None:
        return None, f"filter without Fc: '{rest}'"
    if q is None and bw is not None and bw > 0:
        q = graphic.q_from_bandwidth(bw)
    if q is None:
        q = DEFAULT_Q
    band = Band(btype, freq, gain if (gain is not None and btype.has_gain) else 0.0, q, enabled)
    return band.clamped(), None


def _parse_graphic(rest: str) -> tuple[list[float], list[float]]:
    freqs, gains = [], []
    for pair in rest.split(";"):
        parts = pair.split()
        if len(parts) >= 2:
            try:
                f, g = _num(parts[0]), _num(parts[1])
            except ValueError:
                continue
            if f > 0:
                freqs.append(f)
                gains.append(g)
    order = np.argsort(freqs)
    return [freqs[i] for i in order], [gains[i] for i in order]


def parse(text: str, graphic_bands: int = 127, rate: float = DEFAULT_RATE) -> ParseResult:
    bands: list[Band] = []
    preamp = 0.0
    warnings: list[str] = []
    graphic_curve: tuple[list[float], list[float]] | None = None
    channel_warned = False

    for lineno, raw in enumerate(text.splitlines(), 1):
        line = _strip_comment(raw.lstrip("﻿"))
        if not line or line.startswith(";"):
            continue
        m = _PREAMP_RE.match(line)
        if m:
            preamp += _num(m["v"])
            continue
        m = _FILTER_RE.match(line)
        if m:
            band, err = _parse_filter(m["rest"])
            if err:
                warnings.append(f"line {lineno}: {err}")
            elif band is not None:
                bands.append(band)
            continue
        if line.lower().startswith("graphiceq"):
            _, _, rest = line.partition(":")
            f, g = _parse_graphic(rest)
            if len(f) < 2:
                warnings.append(f"line {lineno}: GraphicEQ needs at least two points")
            else:
                if graphic_curve is not None:
                    warnings.append(f"line {lineno}: multiple GraphicEQ lines; using the last one")
                graphic_curve = (f, g)
            continue
        d = _DIRECTIVE_RE.match(line)
        name = d["name"].strip() if d else line.split()[0]
        if name.lower() == "channel":
            value = line.partition(":")[2].strip().lower()
            if value not in ("all", "") and not channel_warned:
                warnings.append(f"line {lineno}: per-channel filters are not supported; applying to all channels")
                channel_warned = True
            continue
        warnings.append(f"line {lineno}: ignored unsupported directive '{name}'")

    if graphic_curve is not None:
        if bands:
            warnings.append("GraphicEQ combined with filters; filters were folded into the graphic curve")
            freqs = np.asarray(graphic_curve[0])
            extra = state_response_db(EqState(tuple(bands)), freqs, rate)
            graphic_curve = (graphic_curve[0], list(np.asarray(graphic_curve[1]) + extra))
        fitted = graphic.fit_bands(graphic_bands, graphic_curve[0], graphic_curve[1], rate)
        return ParseResult(EqState(fitted, round(preamp, 2), EqMode.GRAPHIC), warnings)
    return ParseResult(EqState(tuple(bands), round(preamp, 2), EqMode.PARAMETRIC), warnings)


def _fmt(v: float, digits: int = 1) -> str:
    s = f"{v:.{digits}f}"
    return "0.0" if s in ("-0.0", "-0.00") else s


def _trim(v: float, digits: int) -> str:
    """Fixed-point with trailing zeros removed: 105.0 -> '105', 0.7070 -> '0.707'."""
    s = f"{v:.{digits}f}".rstrip("0").rstrip(".")
    return s or "0"


def export_parametric(state: EqState) -> str:
    lines = [f"Preamp: {_fmt(state.preamp)} dB"]
    for i, b in enumerate(state.bands, 1):
        code = _EXPORT_CODE[b.type]
        onoff = "ON" if b.enabled else "OFF"
        parts = [f"Filter {i}: {onoff} {code} Fc {_trim(b.freq, 1)} Hz"]
        if b.type.has_gain:
            parts.append(f"Gain {_fmt(b.gain)} dB")
        parts.append(f"Q {_trim(b.q, 4)}")
        lines.append(" ".join(parts))
    return "\n".join(lines) + "\n"


def export_graphic(state: EqState, points: Sequence[float] | None = None, rate: float = DEFAULT_RATE) -> str:
    """GraphicEQ line sampling the full response (bands only; preamp goes on its own line)."""
    freqs = np.asarray(points) if points is not None else _autoeq_points()
    db = state_response_db(EqState(state.bands), freqs, rate)
    pairs = "; ".join(f"{f:g} {_fmt(g)}" for f, g in zip(np.round(freqs).astype(int), db))
    return f"Preamp: {_fmt(state.preamp)} dB\nGraphicEQ: {pairs}\n"


def _autoeq_points() -> np.ndarray:
    # 127 log-spaced points like AutoEQ's GraphicEQ.txt, deduplicated after rounding
    pts = np.unique(np.round(np.geomspace(20, 19871, 127)))
    return pts
