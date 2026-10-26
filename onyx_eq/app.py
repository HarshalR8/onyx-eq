"""Onyx EQ application entry point."""
from __future__ import annotations

import argparse
import fcntl
import os
import signal
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def _single_instance_lock():
    from .core.presets import config_dir

    d = config_dir()
    d.mkdir(parents=True, exist_ok=True)
    f = open(d / "app.lock", "w")
    try:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return None
    return f


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="onyx-eq")
    ap.add_argument("--no-engine", action="store_true", help="UI only; don't touch PipeWire")
    ap.add_argument("files", nargs="*", type=Path, help="APO/AutoEQ file to import on start")
    ap.add_argument("--import", dest="import_file", type=Path, help=argparse.SUPPRESS)
    ap.add_argument("--screenshot", type=Path, help=argparse.SUPPRESS)
    ap.add_argument("--size", default="", help=argparse.SUPPRESS)
    ap.add_argument("--mode", choices=["parametric", "graphic"], help=argparse.SUPPRESS)
    args, qt_args = ap.parse_known_args(argv if argv is not None else sys.argv[1:])

    # Same look on KDE and GNOME: never pick up the desktop's Qt Quick Controls style.
    os.environ["QT_QUICK_CONTROLS_STYLE"] = "Basic"
    from PySide6.QtCore import QTimer, QUrl
    from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication, QIcon
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuickControls2 import QQuickStyle

    from .core.presets import PresetStore, Settings
    from .ui.bridge import Bridge

    QQuickStyle.setStyle("Basic")
    QGuiApplication.setApplicationName("Onyx EQ")
    QGuiApplication.setOrganizationName("onyx-eq")
    QGuiApplication.setDesktopFileName("onyx-eq")
    app = QGuiApplication([sys.argv[0], *qt_args])
    app.setWindowIcon(QIcon(str(HERE / "data" / "onyx-eq.svg")))

    fid = QFontDatabase.addApplicationFont(str(HERE / "ui" / "fonts" / "InterVariable.ttf"))
    families = QFontDatabase.applicationFontFamilies(fid) if fid >= 0 else []
    font = QFont(families[0] if families else "sans-serif")
    font.setPixelSize(15)
    font.setHintingPreference(QFont.PreferNoHinting)
    app.setFont(font)

    lock = None
    if not args.no_engine:
        lock = _single_instance_lock()
        if lock is None:
            print("Onyx EQ is already running.", file=sys.stderr)
            return 1

    bridge = Bridge(settings=Settings(), store=PresetStore())
    if not args.no_engine:
        from .engine.controller import EngineController

        bridge.engine = EngineController(on_status=bridge.engine_status_callback)
    if args.mode:
        bridge.setMode(args.mode)
    to_import = args.import_file or next((f for f in args.files if f.is_file()), None)
    if to_import:
        bridge.importFile(str(to_import.resolve()))

    engine = QQmlApplicationEngine()
    engine.setInitialProperties({"bridge": bridge})
    engine.load(QUrl.fromLocalFile(str(HERE / "ui" / "qml" / "Main.qml")))
    if not engine.rootObjects():
        return 1
    window = engine.rootObjects()[0]
    if args.size:
        w, h = (int(v) for v in args.size.lower().split("x"))
        window.resize(w, h)

    app.aboutToQuit.connect(bridge.shutdown)
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    signal.signal(signal.SIGTERM, lambda *_: app.quit())
    pump = QTimer(interval=200)  # let Python see Unix signals while Qt's loop runs
    pump.timeout.connect(lambda: None)
    pump.start()

    bridge.start_engine()

    if args.screenshot:
        def grab():
            window.grabWindow().save(str(args.screenshot))
            app.quit()

        QTimer.singleShot(1500, grab)

    rc = app.exec()
    del engine
    return rc


if __name__ == "__main__":
    sys.exit(main())
