"""Optional systemd user unit that keeps the EQ running after the window closes (and at login)."""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from . import pipewire as pw

UNIT = "onyx-eq.service"


def unit_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(Path.home(), ".config")
    return Path(base) / "systemd" / "user" / UNIT


def unit_text(conf_path: Path) -> str:
    exe = shutil.which("pipewire") or "/usr/bin/pipewire"
    return f"""[Unit]
Description=Onyx EQ (PipeWire filter-chain)
After=pipewire.service
BindsTo=pipewire.service

[Service]
ExecStart={exe} -c {conf_path}
Restart=on-failure

[Install]
WantedBy=pipewire.service
"""


def available() -> bool:
    return shutil.which("systemctl") is not None


def is_active() -> bool:
    return available() and pw.systemctl_user("is-active", "--quiet", UNIT).returncode == 0


def install(conf_path: Path) -> None:
    path = unit_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(unit_text(conf_path))
    pw.systemctl_user("daemon-reload")
    pw.systemctl_user("enable", UNIT)


def start() -> bool:
    return pw.systemctl_user("restart", UNIT).returncode == 0


def stop() -> None:
    if is_active():
        pw.systemctl_user("stop", UNIT)


def uninstall() -> None:
    if not available():
        return
    pw.systemctl_user("disable", "--now", UNIT)
    unit_path().unlink(missing_ok=True)
    pw.systemctl_user("daemon-reload")
