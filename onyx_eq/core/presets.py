"""JSON presets in ~/.config/onyx-eq/presets/ plus small app settings. No Qt."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from .models import EqState, Preset


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(Path.home(), ".config")
    return Path(base) / "onyx-eq"


def _slug(name: str) -> str:
    s = re.sub(r"[^\w\- ]+", "", name, flags=re.UNICODE).strip().replace(" ", "_")
    return s or "preset"


class PresetStore:
    def __init__(self, directory: Path | None = None):
        self.dir = Path(directory) if directory else config_dir() / "presets"

    def _path(self, name: str) -> Path:
        return self.dir / f"{_slug(name)}.json"

    def names(self) -> list[str]:
        if not self.dir.is_dir():
            return []
        out = []
        for p in self.dir.glob("*.json"):
            try:
                out.append(str(json.loads(p.read_text())["name"]))
            except (OSError, ValueError, KeyError):
                continue
        return sorted(out, key=str.casefold)

    def exists(self, name: str) -> bool:
        return self._path(name).is_file()

    def load(self, name: str) -> Preset:
        return Preset.from_dict(json.loads(self._path(name).read_text()))

    def save(self, preset: Preset) -> Path:
        self.dir.mkdir(parents=True, exist_ok=True)
        path = self._path(preset.name)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(preset.to_dict(), indent=2))
        tmp.replace(path)
        return path

    def delete(self, name: str) -> None:
        self._path(name).unlink(missing_ok=True)

    def rename(self, old: str, new: str) -> None:
        if old == new:
            return
        if self.exists(new):
            raise FileExistsError(new)
        preset = self.load(old)
        self.save(Preset(new, preset.state))
        if self._path(old) != self._path(new):
            self.delete(old)


class Settings:
    """Small key/value JSON file: last state, per-device presets, options."""

    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path else config_dir() / "settings.json"
        try:
            self.data: dict = json.loads(self.path.read_text())
        except (OSError, ValueError):
            self.data = {}

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def set(self, key: str, value) -> None:
        self.data[key] = value
        self.save()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2))
        tmp.replace(self.path)

    # convenience
    def last_state(self) -> EqState | None:
        d = self.data.get("last_state")
        return EqState.from_dict(d) if d else None

    def set_last_state(self, state: EqState) -> None:
        self.set("last_state", state.to_dict())
