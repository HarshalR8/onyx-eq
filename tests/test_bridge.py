import pytest

pytest.importorskip("PySide6")

from onyx_eq.core.presets import PresetStore, Settings
from onyx_eq.ui.bridge import Bridge


@pytest.fixture
def bridge(tmp_path):
    return Bridge(settings=Settings(tmp_path / "s.json"), store=PresetStore(tmp_path / "presets"))


def test_graphic_labels_with_no_bands(bridge):
    # GraphicSliders asks for labels even in parametric mode, where a fresh state has 0 bands
    assert bridge.bandCount == 0
    assert bridge.graphicLabels(0) == []
    assert bridge.graphicLabels(10)[0] == "31.5"


def test_add_undo_redo(bridge):
    bridge.addBand(1000, 3)
    assert bridge.bandCount == 1
    bridge.undo()
    assert bridge.bandCount == 0
    bridge.redo()
    assert bridge.bandCount == 1


class FakeEngine:
    """Records what the bridge asks of the engine; no PipeWire involved."""

    def __init__(self):
        self.outputs = []
        self.rate = 48000.0
        self.output = None

    def set_output(self, name):
        self.outputs.append(name)
        self.output = name

    def submit(self, state, bypass=False):
        pass


def test_follows_system_default_and_switches_device_preset(bridge):
    from onyx_eq.core.models import Band, EqState, Preset

    bridge.engine = FakeEngine()
    bridge.store.save(Preset("Earbuds", EqState((Band(gain=3.0),))))
    bridge.settings.set("device_presets", {"bluez_earbuds": "Earbuds"})
    sinks = [{"name": "alsa_speakers", "description": "Speakers"}, {"name": "bluez_earbuds", "description": "Earbuds"}]

    bridge._on_devices(sinks, "alsa_speakers")  # first poll: just record where we are
    assert bridge.output == "alsa_speakers"
    bridge._on_devices(sinks, "bluez_earbuds")  # user switched the default (e.g. connected earbuds)
    assert bridge.engine.outputs[-1] == "bluez_earbuds"
    assert bridge.output == "bluez_earbuds"
    assert bridge.presetName == "Earbuds"


def test_does_not_follow_default_in_dev_mode(bridge):
    bridge.engine = FakeEngine()
    bridge._follow_default = False
    bridge._on_devices([{"name": "a", "description": "A"}], "a")
    assert bridge.engine.outputs == []
