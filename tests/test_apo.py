from pathlib import Path

import numpy as np
import pytest

from onyx_eq.core import apo
from onyx_eq.core.biquad import state_response_db
from onyx_eq.core.models import Band, BandType, EqMode, EqState

DATA = Path(__file__).parent / "data"


def test_autoeq_parametric_file():
    r = apo.parse((DATA / "HD650 ParametricEQ.txt").read_text())
    assert r.warnings == []
    s = r.state
    assert s.mode is EqMode.PARAMETRIC
    assert s.preamp == -6.1
    assert len(s.bands) == 10
    assert s.bands[0] == Band(BandType.LOW_SHELF, 105, 6.4, 0.70)
    assert s.bands[1] == Band(BandType.PEAKING, 8800, 5.1, 1.42)
    assert all(b.enabled for b in s.bands)


def test_autoeq_graphic_file_is_fitted_closely():
    text = (DATA / "HD650 GraphicEQ.txt").read_text()
    r = apo.parse(text, graphic_bands=127)
    assert r.state.mode is EqMode.GRAPHIC
    assert len(r.state.bands) == 127
    pairs = [p.split() for p in text.split(":", 1)[1].split(";") if p.strip()]
    f = np.array([float(a) for a, _ in pairs])
    g = np.array([float(b) for _, b in pairs])
    got = state_response_db(EqState(r.state.bands), f)
    inside = (f >= 25) & (f <= 16000)
    assert np.max(np.abs(got[inside] - g[inside])) < 0.5
    assert np.sqrt(np.mean((got[inside] - g[inside]) ** 2)) < 0.1


def test_parse_variants_and_warnings():
    text = """
    # comment
    Device: Speakers
    Preamp: -3 dB
    Preamp: -1.5 dB
    Filter 1: ON PK Fc 1000 Hz Gain -2,5 dB Q 1.41   # decimal comma
    Filter 2: OFF LSC Fc 80 Hz Gain 4 dB
    Filter: ON HP Fc 30 Hz
    Filter 4: ON PK Fc 500 Hz Gain 3 dB BW Oct 1.0
    Filter 5: ON XYZ Fc 10 Hz
    Channel: L
    Delay: 5 ms
    Include: other.txt
    """
    r = apo.parse(text)
    s = r.state
    assert s.preamp == -4.5
    assert [b.type for b in s.bands] == [BandType.PEAKING, BandType.LOW_SHELF, BandType.HIGH_PASS, BandType.PEAKING]
    assert s.bands[0].gain == -2.5
    assert s.bands[1].enabled is False and s.bands[1].q == pytest.approx(0.7071, abs=1e-3)
    assert s.bands[2].gain == 0.0
    assert s.bands[3].q == pytest.approx(1.4142, abs=1e-3)
    joined = "\n".join(r.warnings)
    for needle in ("Device", "XYZ", "per-channel", "Delay", "Include"):
        assert needle in joined


def test_parametric_round_trip():
    state = EqState(
        (
            Band(BandType.LOW_SHELF, 105, 6.4, 0.7),
            Band(BandType.PEAKING, 8800, -5.1, 1.42),
            Band(BandType.HIGH_SHELF, 10000, 2.0, 0.7071, enabled=False),
            Band(BandType.LOW_PASS, 18000.5, 0.0, 0.5),
            Band(BandType.HIGH_PASS, 25.5, 0.0, 0.707),
            Band(BandType.NOTCH, 60, 0.0, 10),
            Band(BandType.BAND_PASS, 1000, 0.0, 2),
            Band(BandType.ALL_PASS, 300, 0.0, 0.9),
        ),
        preamp=-6.5,
    )
    text = apo.export_parametric(state)
    back = apo.parse(text)
    assert back.warnings == []
    assert back.state == state


def test_graphic_round_trip():
    state = EqState((Band(BandType.PEAKING, 100, 5, 1), Band(BandType.HIGH_SHELF, 6000, -3, 0.7)), preamp=-5.0)
    back = apo.parse(apo.export_graphic(state), graphic_bands=127).state
    f = np.geomspace(30, 15000, 200)
    assert back.preamp == -5.0
    assert np.max(np.abs(state_response_db(EqState(back.bands), f) - state_response_db(EqState(state.bands), f))) < 0.3
