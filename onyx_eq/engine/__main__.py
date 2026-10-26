"""Headless engine: apply an APO/AutoEQ file and live-edit bands from stdin.

    python -m onyx_eq.engine --preset "HD650 ParametricEQ.txt" [--output SINK] [--no-default]

Commands (one per line):
    list                         show bands
    <n> gain|freq|q <value>      edit band n (1-based)
    <n> on|off                   enable/disable band n
    <n> type peaking|lowshelf|…  change type
    add <freq> <gain> [q]        add a peaking band
    del <n>                      remove band n
    preamp <dB>                  set preamp
    bypass on|off
    outputs                      list output devices
    output <sink node.name>      route EQ to another device
    quit
"""
from __future__ import annotations

import argparse
import signal
import sys
from dataclasses import replace
from pathlib import Path

from ..core import apo
from ..core.models import Band, BandType, EqState
from . import devices
from .controller import EngineController


def _print_state(state: EqState) -> None:
    print(f"Preamp {state.preamp:+.1f} dB, {len(state.bands)} bands")
    for i, b in enumerate(state.bands, 1):
        flag = "" if b.enabled else "  (off)"
        print(f"  {i:3d}  {b.type.display_name:<10} {b.freq:9.1f} Hz  {b.gain:+6.1f} dB  Q {b.q:.3f}{flag}")


def _status(level: str, msg: str) -> None:
    if msg:
        print(f"[{level}] {msg}", file=sys.stderr, flush=True)


def _handle(line: str, state: EqState, ctl: EngineController, bypass: list[bool]) -> EqState | None:
    parts = line.split()
    if not parts:
        return state
    cmd = parts[0].lower()
    if cmd in ("quit", "exit", "q"):
        return None
    if cmd == "list":
        _print_state(state)
    elif cmd == "preamp":
        state = replace(state, preamp=float(parts[1]))
    elif cmd == "bypass":
        bypass[0] = parts[1].lower() in ("on", "1", "true")
    elif cmd == "add":
        q = float(parts[3]) if len(parts) > 3 else 1.0
        state = state.add_band(Band(BandType.PEAKING, float(parts[1]), float(parts[2]), q))
    elif cmd == "del":
        state = state.remove_band(int(parts[1]) - 1)
    elif cmd == "outputs":
        for s in devices.list_sinks():
            mark = "*" if s.name == ctl.output else " "
            print(f" {mark} {s.name}  ({s.description})")
    elif cmd == "output":
        ctl.set_output(parts[1])
    elif cmd.isdigit():
        i = int(cmd) - 1
        b = state.bands[i]
        what = parts[1].lower()
        if what in ("on", "off"):
            b = replace(b, enabled=what == "on")
        elif what == "type":
            b = replace(b, type=BandType(parts[2].lower()))
        else:
            field = {"gain": "gain", "freq": "freq", "q": "q"}[what]
            b = replace(b, **{field: float(parts[2])})
        state = state.with_band(i, b)
    else:
        print(f"unknown command: {cmd}", file=sys.stderr)
        return state
    ctl.submit(state, bypass[0])
    return state


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="onyx-eq-engine", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--preset", type=Path, help="Equalizer APO / AutoEQ file")
    ap.add_argument("--output", help="sink node.name to equalize (default: the current default device)")
    ap.add_argument("--no-default", action="store_true", help="don't change the system default device")
    ap.add_argument("--graphic-bands", type=int, default=127, help="bands used for GraphicEQ files")
    args = ap.parse_args(argv)

    state = EqState()
    if args.preset:
        result = apo.parse(args.preset.read_text(errors="replace"), graphic_bands=args.graphic_bands)
        for w in result.warnings:
            print(f"warning: {w}", file=sys.stderr)
        state = result.state

    ctl = EngineController(on_status=_status)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        ctl.start(state, output=args.output, make_default=not args.no_default)
        ctl.wait_idle(10)
        print(f"Onyx EQ running → {ctl.output}. Type 'list', edits, or 'quit'.", flush=True)
        _print_state(state)
        bypass = [False]
        for line in sys.stdin:
            try:
                new = _handle(line, state, ctl, bypass)
            except (IndexError, ValueError, KeyError) as e:
                print(f"bad command ({e}); see --help", file=sys.stderr)
                continue
            if new is None:
                break
            state = new
            ctl.wait_idle(10)
    except KeyboardInterrupt:
        pass
    finally:
        ctl.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
