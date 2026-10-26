"""Output devices: list sinks, read/set the default sink, retarget the EQ output."""
from __future__ import annotations

import json
from dataclasses import dataclass

from . import pipewire as pw
from .chain_config import SINK_NAME


@dataclass(frozen=True)
class Sink:
    id: int
    name: str
    description: str


def list_sinks(dump: list[dict] | None = None, include_virtual: bool = False) -> list[Sink]:
    dump = dump if dump is not None else pw.pw_dump()
    out = []
    for o in dump:
        if o.get("type") != "PipeWire:Interface:Node":
            continue
        p = pw.node_props(o)
        if p.get("media.class") != "Audio/Sink" or p.get("node.name") == SINK_NAME:
            continue
        if not include_virtual and p.get("node.virtual"):
            continue
        name = p.get("node.name", "")
        desc = p.get("node.description") or p.get("node.nick") or name
        out.append(Sink(int(o["id"]), name, desc))
    return sorted(out, key=lambda s: s.description.casefold())


def _metadata_value(dump: list[dict], metadata_name: str, key: str):
    for o in dump:
        if o.get("type") != "PipeWire:Interface:Metadata":
            continue
        if (o.get("props") or {}).get("metadata.name") != metadata_name:
            continue
        for entry in o.get("metadata") or []:
            if entry.get("key") == key:
                v = entry.get("value")
                if isinstance(v, str):
                    try:
                        v = json.loads(v)
                    except ValueError:
                        pass
                return v
    return None


def default_sink_name(dump: list[dict] | None = None) -> str | None:
    v = _metadata_value(dump if dump is not None else pw.pw_dump(), "default", "default.audio.sink")
    if isinstance(v, dict):
        return v.get("name")
    return v if isinstance(v, str) else None


def set_default_sink(name: str, dump: list[dict] | None = None) -> bool:
    node = pw.find_node(name, dump)
    if node is None:
        return False
    return pw.run(["wpctl", "set-default", str(node)]).returncode == 0


def configured_default_sink_name(dump: list[dict] | None = None) -> str | None:
    """The default the user (or an app) chose, which WirePlumber remembers across restarts."""
    v = _metadata_value(dump if dump is not None else pw.pw_dump(), "default", "default.configured.audio.sink")
    if isinstance(v, dict):
        return v.get("name")
    return v if isinstance(v, str) else None


def set_filter_target(filter_node_id: int, sink_name: str) -> bool:
    """Point the smart filter at another device without a reload."""
    value = json.dumps({"node.name": sink_name})
    cmd = ["pw-metadata", "-n", "filters", str(filter_node_id), "filter.smart.target", value, "Spa:String:JSON"]
    return pw.run(cmd).returncode == 0


def clear_filter_target(filter_node_id: int) -> None:
    """Drop our metadata entry so it can't stick to a future node that reuses the id."""
    pw.run(["pw-metadata", "-n", "filters", "-d", str(filter_node_id), "filter.smart.target"])


def reset_volume(node_id: int) -> bool:
    """Unity gain, unmuted. The smart filter is hidden from volume menus, so a volume WirePlumber
    restored from an older version (when Onyx EQ was the default output) would silently stick."""
    ok = pw.run(["wpctl", "set-volume", str(node_id), "1.0"]).returncode == 0
    return pw.run(["wpctl", "set-mute", str(node_id), "0"]).returncode == 0 and ok


def node_volume(node_id: int, dump: list[dict] | None = None) -> tuple[list[float], bool] | None:
    """(linear channel volumes, muted) of a node."""
    for o in dump if dump is not None else pw.pw_dump():
        if o.get("id") == node_id:
            for pr in ((o.get("info") or {}).get("params") or {}).get("Props") or []:
                if "channelVolumes" in pr:
                    return list(pr["channelVolumes"]), bool(pr.get("mute", False))
    return None
