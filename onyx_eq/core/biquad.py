"""RBJ cookbook biquads, mirroring PipeWire's spa/plugins/audioconvert/biquad.c exactly
(same Q definition for every type, same edge-case handling). See docs/pipewire-notes.md.
"""
from __future__ import annotations

import math
from typing import Iterable, Sequence

import numpy as np

from .models import Band, BandType, EqState

DEFAULT_RATE = 48000.0
CURVE_POINTS = 512
CURVE_MIN_HZ = 20.0
CURVE_MAX_HZ = 20000.0
_DEFAULT_Q = 0.707106781186548

Coeffs = tuple[tuple[float, float, float], tuple[float, float, float]]
_UNITY: Coeffs = ((1.0, 0.0, 0.0), (1.0, 0.0, 0.0))


def _const(g: float) -> Coeffs:
    return ((g, 0.0, 0.0), (1.0, 0.0, 0.0))


def coefficients(band: Band, rate: float = DEFAULT_RATE) -> Coeffs:
    """Return ((b0, b1, b2), (a0, a1, a2)) normalised so a0 == 1."""
    if not band.enabled:
        return _UNITY
    t = band.type
    f = band.freq / (rate / 2.0)
    q = band.q
    A = 10.0 ** (band.gain / 40.0)

    if t is BandType.BAND_PASS:
        f = max(0.0, f)
        q = max(0.0, q)
        if f <= 0 or f >= 1:
            return _const(0.0)
        if q <= 0:
            return _UNITY
    else:
        f = max(0.0, min(f, 1.0))

    if t is BandType.LOW_PASS:
        if f in (0.0, 1.0):
            return _const(f)
    elif t is BandType.HIGH_PASS:
        if f in (0.0, 1.0):
            return _const(1.0 - f)
    elif t is BandType.LOW_SHELF:
        if f == 1:
            return _const(A * A)
        if f <= 0:
            return _UNITY
    elif t is BandType.HIGH_SHELF:
        if f == 1:
            return _UNITY
        if f <= 0:
            return _const(A * A)
    elif t in (BandType.PEAKING, BandType.NOTCH, BandType.ALL_PASS):
        q = max(0.0, q)
        if f <= 0 or f >= 1:
            return _UNITY
        if q <= 0:
            return _const({BandType.PEAKING: A * A, BandType.NOTCH: 0.0, BandType.ALL_PASS: -1.0}[t])

    if q <= 0:
        q = _DEFAULT_Q
    w0 = math.pi * f
    alpha = math.sin(w0) / (2.0 * q)
    k = math.cos(w0)

    if t is BandType.LOW_PASS:
        b = ((1 - k) / 2, 1 - k, (1 - k) / 2)
        a = (1 + alpha, -2 * k, 1 - alpha)
    elif t is BandType.HIGH_PASS:
        b = ((1 + k) / 2, -(1 + k), (1 + k) / 2)
        a = (1 + alpha, -2 * k, 1 - alpha)
    elif t is BandType.BAND_PASS:
        b = (alpha, 0.0, -alpha)
        a = (1 + alpha, -2 * k, 1 - alpha)
    elif t is BandType.LOW_SHELF:
        k2 = 2 * math.sqrt(A) * alpha
        ap, am = A + 1, A - 1
        b = (A * (ap - am * k + k2), 2 * A * (am - ap * k), A * (ap - am * k - k2))
        a = (ap + am * k + k2, -2 * (am + ap * k), ap + am * k - k2)
    elif t is BandType.HIGH_SHELF:
        k2 = 2 * math.sqrt(A) * alpha
        ap, am = A + 1, A - 1
        b = (A * (ap + am * k + k2), -2 * A * (am + ap * k), A * (ap + am * k - k2))
        a = (ap - am * k + k2, 2 * (am - ap * k), ap - am * k - k2)
    elif t is BandType.PEAKING:
        b = (1 + alpha * A, -2 * k, 1 - alpha * A)
        a = (1 + alpha / A, -2 * k, 1 - alpha / A)
    elif t is BandType.NOTCH:
        b = (1.0, -2 * k, 1.0)
        a = (1 + alpha, -2 * k, 1 - alpha)
    elif t is BandType.ALL_PASS:
        b = (1 - alpha, -2 * k, 1 + alpha)
        a = (1 + alpha, -2 * k, 1 - alpha)
    else:  # pragma: no cover
        return _UNITY

    inv = 1.0 / a[0]
    return (b[0] * inv, b[1] * inv, b[2] * inv), (1.0, a[1] * inv, a[2] * inv)


def log_frequencies(n: int = CURVE_POINTS, lo: float = CURVE_MIN_HZ, hi: float = CURVE_MAX_HZ) -> np.ndarray:
    return np.geomspace(lo, hi, n)


_FLOOR_DB = -120.0


def magnitude_db(band: Band, freqs: Sequence[float] | np.ndarray, rate: float = DEFAULT_RATE) -> np.ndarray:
    (b0, b1, b2), (_, a1, a2) = coefficients(band, rate)
    w = 2.0 * np.pi * np.asarray(freqs, dtype=float) / rate
    z1 = np.exp(-1j * w)
    z2 = z1 * z1
    h = (b0 + b1 * z1 + b2 * z2) / (1.0 + a1 * z1 + a2 * z2)
    mag = np.abs(h)
    with np.errstate(divide="ignore"):
        db = 20.0 * np.log10(mag)
    return np.maximum(db, _FLOOR_DB)


def total_response_db(
    bands: Iterable[Band],
    freqs: Sequence[float] | np.ndarray,
    preamp: float = 0.0,
    rate: float = DEFAULT_RATE,
) -> np.ndarray:
    out = np.full(len(freqs), float(preamp))
    for band in bands:
        if band.enabled:
            out = out + magnitude_db(band, freqs, rate)
    return np.maximum(out, _FLOOR_DB)


def state_response_db(state: EqState, freqs: Sequence[float] | np.ndarray, rate: float = DEFAULT_RATE) -> np.ndarray:
    return total_response_db(state.bands, freqs, state.preamp, rate)


def max_boost_db(bands: Iterable[Band], rate: float = DEFAULT_RATE) -> float:
    """Highest point of the band curve (without preamp), sampled densely across 10 Hz–22 kHz."""
    freqs = log_frequencies(2048, 10.0, min(22000.0, rate / 2 * 0.999))
    return float(np.max(total_response_db(bands, freqs, 0.0, rate)))


def auto_preamp(bands: Iterable[Band], rate: float = DEFAULT_RATE) -> float:
    """Negative of the maximum boost, so the peak sits at 0 dB. Never positive."""
    return round(-max(0.0, max_boost_db(bands, rate)), 1)
