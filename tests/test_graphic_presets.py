import numpy as np
import pytest

from onyx_eq.core import graphic
from onyx_eq.core.biquad import total_response_db
from onyx_eq.core.models import Band, BandType, EqMode, EqState, Preset
from onyx_eq.core.presets import PresetStore, Settings


@pytest.mark.parametrize("n", [10, 15, 31, 64, 127, 7])
def test_layouts(n):
    f = graphic.layout(n)
    assert len(f) == n
    assert list(f) == sorted(f)
    assert 20 <= f[0] and f[-1] <= 20000


def test_iso_layouts_and_q():
    assert graphic.layout(10)[0] == 31.5
    assert graphic.layout(31)[17] == 1000
    assert graphic.q_from_bandwidth(1.0) == pytest.approx(1.4142, abs=1e-4)
    # ISO layouts: bandwidth = 1.5x the spacing (octave -> Q 0.92, third-octave -> Q 2.87)
    assert graphic.q_for_layout(graphic.layout(10))[0] == pytest.approx(0.92, abs=0.03)
    assert graphic.q_for_layout(graphic.layout(31))[5] == pytest.approx(2.87, abs=0.05)
    # dense layouts overlap more (bandwidth = 2x spacing)
    f = graphic.layout(127)
    spacing = np.log2(f[-1] / f[0]) / 126
    assert graphic.q_for_layout(f)[0] == pytest.approx(graphic.q_from_bandwidth(2 * spacing), rel=1e-3)


def test_q_compensates_for_warping_near_nyquist():
    # same bandwidth in octaves -> lower Q up high; identical to the textbook value down low
    assert graphic.q_for_band(16000, 1.0) < 0.8 * graphic.q_for_band(100, 1.0)
    assert graphic.q_for_band(50, 1.0) == pytest.approx(graphic.q_from_bandwidth(1.0), rel=1e-3)


def test_flat_bands_are_flat():
    bands = graphic.bands_for(31)
    assert np.allclose(total_response_db(bands, np.geomspace(20, 20000, 100)), 0)


def test_from_parametric_tracks_curve():
    src = [Band(BandType.LOW_SHELF, 120, 5, 0.7), Band(BandType.PEAKING, 3000, -4, 1.2)]
    for n in (31, 127):
        out = graphic.from_parametric(src, n)
        f = np.geomspace(40, 12000, 200)
        err = total_response_db(out, f) - total_response_db(src, f)
        assert np.max(np.abs(err)) < (0.5 if n == 31 else 0.2)


def test_preset_store(tmp_path):
    store = PresetStore(tmp_path)
    assert store.names() == []
    st = EqState((Band(BandType.PEAKING, 1000, 3, 1),), -3.0, EqMode.GRAPHIC)
    store.save(Preset("My Preset/1", st))
    store.save(Preset("bass", EqState()))
    assert store.names() == ["bass", "My Preset/1"]
    assert store.load("My Preset/1").state == st
    store.rename("bass", "Bass Boost")
    assert store.names() == ["Bass Boost", "My Preset/1"]
    with pytest.raises(FileExistsError):
        store.rename("Bass Boost", "My Preset/1")
    store.delete("Bass Boost")
    assert store.names() == ["My Preset/1"]


def test_settings(tmp_path):
    s = Settings(tmp_path / "s.json")
    assert s.last_state() is None
    st = EqState((Band(BandType.NOTCH, 60, 0, 8),), -1.0)
    s.set_last_state(st)
    s.set("device_presets", {"hw": "bass"})
    s2 = Settings(tmp_path / "s.json")
    assert s2.last_state() == st
    assert s2.get("device_presets") == {"hw": "bass"}


def test_state_editing_clamps():
    st = EqState().add_band(Band(BandType.PEAKING, 5, 99, 1000))
    b = st.bands[0]
    assert (b.freq, b.gain, b.q) == (10.0, 30.0, 30.0)
    st = st.with_band(0, Band(gain=1)).add_band(Band()).remove_band(0)
    assert len(st.bands) == 1 and st.bands[0].gain == 0
