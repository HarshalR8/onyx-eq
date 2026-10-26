import numpy as np

from onyx_eq.core.biquad import coefficients, total_response_db
from onyx_eq.core.models import Band, BandType, EqState
from onyx_eq.engine.chain_config import (
    assign_slots,
    build_config,
    neutral,
    params_for,
    plan_layout,
    pool_size,
)
from onyx_eq.engine.pipewire import set_param_command


def test_pool_sizes():
    assert pool_size(0) == 16 and pool_size(16) == 16 and pool_size(17) == 32
    assert pool_size(127) == 128 and pool_size(600) == 600


def test_layout_has_room_and_spares():
    bands = [Band(BandType.PEAKING)] * 10 + [Band(BandType.NOTCH)]
    layout = plan_layout(bands)
    assert layout.count(BandType.PEAKING) >= 10
    assert layout.count(BandType.NOTCH) == 1
    assert layout.count(BandType.LOW_SHELF) == 2
    assert len(layout) >= 16
    # adding peaking bands up to the pool stays live
    assert assign_slots(bands + [Band()] * 4, layout) is not None
    # a type not in the layout needs a reload
    assert assign_slots(bands + [Band(BandType.ALL_PASS)], layout) is None


def test_assignment_is_unique_and_type_matched():
    bands = [Band(BandType.LOW_SHELF), Band(), Band(BandType.HIGH_SHELF), Band(), Band(BandType.LOW_SHELF)]
    layout = plan_layout(bands)
    slots = assign_slots(bands, layout)
    assert len(set(slots)) == len(bands)
    assert all(layout[s] is b.type for s, b in zip(slots, bands))


def _chain_response(layout, params, f):
    """Simulate the generated chain with the app's own maths."""
    total = 20 * np.log10(params["preamp:Mult"]) * np.ones(len(f))
    for i, t in enumerate(layout):
        b = Band(t, params[f"band_{i}:Freq"], params[f"band_{i}:Gain"], params[f"band_{i}:Q"])
        (b0, b1, b2), (_, a1, a2) = coefficients(b)
        z = np.exp(-1j * 2 * np.pi * f / 48000)
        total += 20 * np.log10(np.abs((b0 + b1 * z + b2 * z * z) / (1 + a1 * z + a2 * z * z)))
    return total


def test_params_reproduce_state_and_bypass_is_flat():
    st = EqState(
        (
            Band(BandType.LOW_SHELF, 100, 4, 0.7),
            Band(BandType.PEAKING, 1000, -3, 2),
            Band(BandType.PEAKING, 3000, 6, 2, enabled=False),
            Band(BandType.HIGH_PASS, 30, 0, 0.7),
        ),
        preamp=-4,
    )
    layout = plan_layout(st.bands)
    slots = assign_slots(st.bands, layout)
    f = np.geomspace(20, 20000, 100)
    p = params_for(st, layout, slots)
    assert np.allclose(_chain_response(layout, p, f), total_response_db(st.bands, f, -4), atol=1e-6)
    pb = params_for(st, layout, slots, bypass=True)
    assert np.allclose(_chain_response(layout, pb, f), 0, atol=1e-9)


def test_every_neutral_is_unity():
    for t in BandType:
        f, q, g = neutral(t)
        b, a = coefficients(Band(t, f, g, q))
        assert b == a or (b, a) == ((1.0, 0.0, 0.0), (1.0, 0.0, 0.0)), t


def test_config_text():
    st = EqState((Band(BandType.PEAKING, 100, 3, 1),))
    layout = plan_layout(st.bands)
    p = params_for(st, layout, assign_slots(st.bands, layout))
    text = build_config(layout, p, target="alsa_output.foo")
    assert 'node.name   = "onyx_eq"' in text
    # a WirePlumber smart filter on the device, which stays the default (and keeps its volume)
    assert "filter.smart = true" in text
    assert 'filter.smart.target = { node.name = "alsa_output.foo" }' in text
    assert "target.object" not in text
    assert "label = bq_lowshelf" in text and "label = linear" in text
    assert text.count("{ output =") == len(layout)  # preamp + N slots -> N links
    assert '"Gain" = 3.0' in text
    assert text.count("{") == text.count("}")


def test_set_param_command():
    cmd = set_param_command(42, {"band_0:Gain": 1.5, "preamp:Mult": 1})
    assert cmd == 'set-param 42 Props { params = [ "band_0:Gain" 1.5 "preamp:Mult" 1.0 ] }'
