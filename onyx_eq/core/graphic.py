"""Graphic-EQ band layouts and curve fitting."""
from __future__ import annotations

import math
from typing import Sequence

import numpy as np

from .biquad import DEFAULT_RATE, magnitude_db, total_response_db
from .models import Band, BandType, MAX_GAIN, MIN_GAIN, clamp

ISO_10 = (31.5, 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000)
ISO_15 = (25, 40, 63, 100, 160, 250, 400, 630, 1000, 1600, 2500, 4000, 6300, 10000, 16000)
ISO_31 = (
    20, 25, 31.5, 40, 50, 63, 80, 100, 125, 160, 200, 250, 315, 400, 500, 630, 800,
    1000, 1250, 1600, 2000, 2500, 3150, 4000, 5000, 6300, 8000, 10000, 12500, 16000, 20000,
)
PRESET_COUNTS = (10, 15, 31, 64, 127)


def layout(count: int, lo: float = 20.0, hi: float = 20000.0) -> tuple[float, ...]:
    """Centre frequencies for an N-band graphic EQ (ISO where standard, else log-spaced)."""
    if count < 1:
        raise ValueError("band count must be >= 1")
    iso = {10: ISO_10, 15: ISO_15, 31: ISO_31}.get(count)
    if iso:
        return tuple(float(f) for f in iso)
    if count == 1:
        return (1000.0,)
    return tuple(float(f) for f in np.geomspace(lo, hi, count))


def q_from_bandwidth(octaves: float) -> float:
    """Q for a bandwidth given in octaves (the usual N = 2^BW formula)."""
    n = 2.0 ** octaves
    return math.sqrt(n) / (n - 1.0)


# Bandwidth as a multiple of the spacing between centres. With Q from the spacing alone (1x) the
# summed response ripples by ~1 dB between centres; dense layouts need the most overlap.
ISO_OVERLAP = 1.5
DENSE_OVERLAP = 2.0


def layout_bandwidth(freqs: Sequence[float]) -> float:
    """Bandwidth in octaves for every band of a layout, from the average spacing."""
    if len(freqs) < 2:
        return 1.0
    octaves = math.log2(freqs[-1] / freqs[0]) / (len(freqs) - 1)
    iso = tuple(freqs) in (ISO_10, ISO_15, ISO_31)
    return octaves * (ISO_OVERLAP if iso else DENSE_OVERLAP)


def q_for_band(freq: float, octaves: float, rate: float = DEFAULT_RATE) -> float:
    """Q giving `octaves` of *digital* bandwidth at `freq`.

    The bilinear transform squeezes bands near Nyquist, so a fixed Q gets narrower up there and a
    dense graphic EQ ripples above ~10 kHz. This is RBJ's bandwidth form solved for Q; well below
    Nyquist it equals q_from_bandwidth().
    """
    w0 = 2 * math.pi * min(freq, rate / 2 * 0.999) / rate
    return 1.0 / (2.0 * math.sinh(math.log(2) / 2 * octaves * w0 / math.sin(w0)))


def q_for_layout(freqs: Sequence[float], rate: float = DEFAULT_RATE) -> list[float]:
    bw = layout_bandwidth(freqs)
    return [q_for_band(f, bw, rate) for f in freqs]


def bands_for(count: int, gains: Sequence[float] | None = None, rate: float = DEFAULT_RATE) -> tuple[Band, ...]:
    freqs = layout(count)
    qs = q_for_layout(freqs, rate)
    gains = list(gains) if gains is not None else [0.0] * count
    return tuple(Band(BandType.PEAKING, f, g, q).clamped() for f, g, q in zip(freqs, gains, qs))


def fit_gains(
    centres: Sequence[float],
    qs: Sequence[float],
    target_freqs: Sequence[float],
    target_db: Sequence[float],
    rate: float = DEFAULT_RATE,
    iterations: int = 6,
) -> list[float]:
    """Gains for fixed peaking bands so their summed response best matches a target curve.

    Peaking filters overlap, so slider gain != curve height. We solve a least-squares problem on
    each band's per-dB shape, then refine a few times because the shape changes slightly with gain.
    """
    centres = list(centres)
    n = len(centres)
    tf = np.asarray(target_freqs, dtype=float)
    td = np.asarray(target_db, dtype=float)
    # Fit only between the outer centres: peaking filters return to 0 dB at DC and Nyquist, so
    # asking the edge bands to hold a level beyond their centre makes their gains run away.
    lo = max(min(centres), 10.0)
    hi = min(max(centres), rate / 2 * 0.9)
    grid = np.geomspace(lo, hi, max(256, 4 * n))
    target = np.interp(np.log(grid), np.log(tf), td)

    gains = np.interp(np.log(centres), np.log(grid), target)
    # light smoothness + ridge terms keep neighbouring sliders from fighting each other
    diff = np.diff(np.eye(n), axis=0)
    reg = 0.1 * diff.T @ diff + 1e-3 * np.eye(n)
    for _ in range(iterations):
        basis = np.empty((len(grid), n))
        for j, (f, g, q) in enumerate(zip(centres, gains, qs)):
            ref = g if abs(g) > 0.5 else 1.0
            basis[:, j] = magnitude_db(Band(BandType.PEAKING, f, ref, q), grid, rate) / ref
        new = np.clip(np.linalg.solve(basis.T @ basis + reg, basis.T @ target), MIN_GAIN, MAX_GAIN)
        done = np.max(np.abs(new - gains)) < 1e-3
        gains = new
        if done:
            break
    return [round(float(clamp(g, MIN_GAIN, MAX_GAIN)), 2) for g in gains]


def fit_bands(count: int, target_freqs: Sequence[float], target_db: Sequence[float], rate: float = DEFAULT_RATE) -> tuple[Band, ...]:
    freqs = layout(count)
    return bands_for(count, fit_gains(freqs, q_for_layout(freqs, rate), target_freqs, target_db, rate), rate)


def from_parametric(bands: Sequence[Band], count: int, rate: float = DEFAULT_RATE) -> tuple[Band, ...]:
    """Approximate an arbitrary band set with an N-band graphic EQ."""
    grid = np.geomspace(20.0, 20000.0, 512)
    return fit_bands(count, grid, total_response_db(bands, grid, 0.0, rate), rate)
