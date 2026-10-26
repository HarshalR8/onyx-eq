import numpy as np
import pytest

from onyx_eq.core.biquad import (
    auto_preamp,
    coefficients,
    log_frequencies,
    magnitude_db,
    max_boost_db,
    total_response_db,
)
from onyx_eq.core.models import Band, BandType


def at(band, f, rate=48000):
    return float(magnitude_db(band, [f], rate)[0])


def test_peaking_hits_gain_at_centre():
    assert at(Band(BandType.PEAKING, 1000, 6.0, 1.0), 1000) == pytest.approx(6.0, abs=1e-6)
    assert at(Band(BandType.PEAKING, 1000, -9.0, 4.0), 1000) == pytest.approx(-9.0, abs=1e-6)


def test_values_measured_through_pipewire():
    # docs/pipewire-notes.md: white noise through the real filter-chain, 8192-pt FFT bins
    bands = [Band(BandType.PEAKING, 100, 12.0, 1.0), Band(BandType.PEAKING, 1000, -6.0, 1.0)]
    measured = {52.73: 4.41, 99.61: 11.74, 199.22: 3.71, 498.05: -1.21, 1001.95: -5.83, 1998.05: -1.83, 10001.95: -0.05}
    got = total_response_db(bands, list(measured))
    for (f, m), g in zip(measured.items(), got):
        assert g == pytest.approx(m, abs=0.25), f


def test_shelves_reach_full_gain_far_from_corner():
    ls = Band(BandType.LOW_SHELF, 200, 6.0, 0.707)
    hs = Band(BandType.HIGH_SHELF, 2000, -4.0, 0.707)
    assert at(ls, 20) == pytest.approx(6.0, abs=0.05)
    assert at(ls, 15000) == pytest.approx(0.0, abs=0.05)
    assert at(hs, 20000) == pytest.approx(-4.0, abs=0.1)
    assert at(hs, 50) == pytest.approx(0.0, abs=0.05)
    # RBJ shelves are -/+ half gain at the corner frequency
    assert at(ls, 200) == pytest.approx(3.0, abs=0.05)


def test_pass_filters():
    lp = Band(BandType.LOW_PASS, 1000, 0, 0.7071)
    hp = Band(BandType.HIGH_PASS, 1000, 0, 0.7071)
    assert at(lp, 1000) == pytest.approx(-3.01, abs=0.05)
    assert at(hp, 1000) == pytest.approx(-3.01, abs=0.05)
    assert at(lp, 50) == pytest.approx(0, abs=0.05)
    assert at(lp, 10000) < -35
    assert at(hp, 100) < -35


def test_notch_bandpass_allpass():
    assert at(Band(BandType.NOTCH, 1000, 0, 2), 1000) <= -100
    assert at(Band(BandType.BAND_PASS, 1000, 0, 2), 1000) == pytest.approx(0, abs=1e-6)
    f = log_frequencies(64)
    assert np.allclose(magnitude_db(Band(BandType.ALL_PASS, 1000, 0, 1), f), 0, atol=1e-9)


def test_gain_ignored_for_gainless_types():
    a = magnitude_db(Band(BandType.LOW_PASS, 1000, 12.0, 0.7), [100, 1000])
    b = magnitude_db(Band(BandType.LOW_PASS, 1000, 0.0, 0.7), [100, 1000])
    assert np.allclose(a, b)


@pytest.mark.parametrize(
    "band",
    [
        Band(BandType.PEAKING, 1000, 0.0, 1),
        Band(BandType.LOW_SHELF, 1000, 0.0, 1),
        Band(BandType.HIGH_SHELF, 1000, 0.0, 1),
        Band(BandType.LOW_PASS, 192000, 0.0, 1),
        Band(BandType.HIGH_PASS, 0.0, 0.0, 1),
        Band(BandType.NOTCH, 0.0, 0.0, 1),
        Band(BandType.ALL_PASS, 0.0, 0.0, 1),
        Band(BandType.BAND_PASS, 1000, 0.0, 0.0),
    ],
)
def test_neutral_settings_are_unity(band):
    # the engine relies on these to disable slots live (see docs/pipewire-notes.md)
    assert is_unity(coefficients(band))


def is_unity(c):
    """Exactly pass-through: numerator == denominator (pole/zero cancel) or literally 1."""
    b, a = c
    return b == a or c == ((1.0, 0.0, 0.0), (1.0, 0.0, 0.0))


def test_disabled_band_is_flat_and_rate_matters():
    assert np.allclose(magnitude_db(Band(BandType.PEAKING, 1000, 9, 1, enabled=False), log_frequencies(32)), 0)
    b = Band(BandType.PEAKING, 15000, 9, 1)
    assert at(b, 18000, 44100) != pytest.approx(at(b, 18000, 48000), abs=0.01)


def test_auto_preamp():
    bands = [Band(BandType.PEAKING, 100, 6.0, 1), Band(BandType.PEAKING, 120, 3.0, 1)]
    assert max_boost_db(bands) > 6.0
    assert auto_preamp(bands) == pytest.approx(-max_boost_db(bands), abs=0.06)
    assert auto_preamp([Band(BandType.PEAKING, 100, -6.0, 1)]) == 0.0
