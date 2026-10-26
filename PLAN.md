# Onyx EQ — Build Plan

> Working name. A system-wide parametric + graphic equalizer for Linux, in the spirit of Equalizer APO, with a pure-black, Apple-style UI.
> This file is the source of truth for Claude Code. Work phase by phase; don't start a phase until the previous one meets its acceptance criteria.

---

## 1. Goals

- **Unlimited bands.** Parametric mode with any number of bands; graphic mode with any band count (10, 15, 31, 64, 127, custom).
- **Smooth parametric editing.** Drag points on a live frequency-response curve; audio updates while dragging with no dropouts.
- **Equalizer APO compatibility.** Import/export APO config files and AutoEQ `ParametricEQ.txt` / `GraphicEQ.txt`.
- **No custom DSP.** All audio processing runs in PipeWire's built-in `filter-chain` biquads. The app is a UI + config/controller.
- **Design:** OLED black, Apple-style, calm, fast. Works on both KDE and GNOME (one UI, no per-desktop variants for now).

### Non-goals (for v1)
- Convolution / FIR, room correction, compressor, crossfeed.
- PulseAudio-only systems (PipeWire required).
- Per-app EQ.

---

## 2. Tech stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11+ | Fast to iterate |
| UI | PySide6 (Qt 6.5+) + **QML** | Full control over styling; pure-black custom theme is easy; runs on KDE and GNOME |
| Math | numpy | Biquad response curves for the UI |
| Audio engine | PipeWire `libpipewire-module-filter-chain` | Built-in `bq_peaking`, `bq_lowshelf`, `bq_highshelf`, `bq_lowpass`, `bq_highpass`, `bq_notch`, `bq_bandpass`, `bq_allpass` |
| Control | `pw-cli` / `pw-dump` via subprocess (wrap in one module) | No reliable Python PipeWire bindings; keeps it swappable later |
| Tests | pytest | Parser + math + config generator are pure functions |
| Packaging | `pyproject.toml`, then AppImage; Flatpak later | Flatpak needs host PipeWire access; defer |

Dependency notes (added during the build):
- **PySide6-Essentials** instead of the full `PySide6` meta-package: QtQuick, Controls, Shapes and
  Dialogs are all in Essentials, and it skips ~400 MB of WebEngine/Addons. Needs Qt ≥ 6.6 for
  `Shape.CurveRenderer` (antialiased curve) and `font.features` (tabular figures).
- **Inter** (`onyx_eq/ui/fonts/InterVariable.ttf`, SIL OFL, licence alongside) is bundled per §4.
- **pytest** is a dev-only extra. The AppImage script installs `python-appimage` and `build` at build time only.

---

## 3. Architecture

```
onyx_eq/
  core/
    models.py        # Band, BandType, Preset, EqState (dataclasses)
    biquad.py        # RBJ cookbook coefficients + magnitude response (numpy)
    apo.py           # APO / AutoEQ parse + export
    graphic.py       # graphic-mode band layouts (ISO 10/15/31, log-spaced N)
    presets.py       # load/save JSON presets in ~/.config/onyx-eq/presets/
  engine/
    chain_config.py  # EqState -> filter-chain .conf text
    pipewire.py      # spawn/stop chain process, find node id, set params live
    devices.py       # list sinks, set default sink (pw-dump / wpctl)
  ui/
    bridge.py        # QObject exposing state/actions to QML
    qml/
      Main.qml
      theme/Theme.qml          # all colours, radii, fonts, spacing
      components/CurveView.qml # the frequency-response editor
      components/BandList.qml
      components/BandInspector.qml
      components/Toolbar.qml
      components/PresetSheet.qml
  app.py
tests/
```

Rules:
- `core/` has **no** Qt or subprocess imports. Everything there is unit-tested.
- `engine/` is the only place that touches PipeWire.
- QML never computes audio math; it asks the bridge for curve points.

### 3.1 How audio flows

1. App writes `~/.config/onyx-eq/chain.conf` (a filter-chain config) creating a virtual sink called **"Onyx EQ"**.
2. App runs `pipewire -c ~/.config/onyx-eq/chain.conf` as a child process (later: optional systemd user unit so EQ persists after the window closes).
3. ~~User (or app) sets "Onyx EQ" as the default output.~~ **Changed:** the chain is a WirePlumber smart
   filter (`filter.smart.target` = the hardware sink). The hardware stays the default, so its volume slider
   is the real volume. Making Onyx EQ the default gave it its own volume, so its 100% was only whatever the
   hardware was set to. The EQ follows the system default device. See `docs/pipewire-notes.md` → Routing.

### 3.2 Live updates without reloading

- Each band is a named node in the graph: `band_0`, `band_1`, …
- Changing **Gain / Freq / Q** on an existing band: set the control live on the running node, e.g.
  `pw-cli set-param <node-id> Props '{ params = [ "band_3:Freq" 1200.0 "band_3:Gain" -2.5 ] }'`
  (Phase 0 must verify the exact syntax against the installed PipeWire version.)
- **Slot pool:** generate the chain with a pool of slots (e.g. next of 16/32/64/128 above the band count). Unused or disabled slots are `bq_peaking` with Gain 0 dB, which is a pass-through. Adding/removing/disabling bands then only needs live param changes, not a reload.
- Changing a band's **type** or exceeding the pool size requires a reload. Do it quickly (write config, restart child, re-link) and keep it rare.
- **Throttle** drag updates to ~60 Hz and coalesce: only send the latest value per band per tick.

### 3.3 Curve maths

- Use RBJ Audio EQ Cookbook formulas at 48 kHz for each band type.
- Evaluate magnitude at ~512 log-spaced points from 20 Hz to 20 kHz; total curve = sum of band dB + preamp.
- Must match what PipeWire actually applies (same formulas, same Q definition). Add a test comparing against known values.

---

## 4. Design spec (OLED black, Apple-style)

Put every value in `Theme.qml`. No hard-coded colours elsewhere.

**Colours**
- Background: `#000000` (true black, everywhere)
- Raised surface / cards: `#1C1C1E`; secondary surface: `#2C2C2E`
- Separators: `#38383A` at 1px, or `rgba(255,255,255,0.08)`
- Text: primary `#FFFFFF`, secondary `rgba(235,235,245,0.6)`, tertiary `rgba(235,235,245,0.3)`
- Accent: `#0A84FF` (system blue). Destructive: `#FF453A`. Positive: `#30D158`
- Band colours (cycle): `#0A84FF #30D158 #FF9F0A #FF375F #BF5AF2 #64D2FF #FFD60A #AC8E68`

**Type**
- Font: Inter (bundle it; SF Pro can't be redistributed on Linux). Fallback: system sans.
- Sizes: title 28 semibold, headline 17 semibold, body 15, caption 12. Numbers use tabular figures.

**Shape & spacing**
- Corner radius: 12 (controls), 16 (cards), 22 (sheets)
- 8-pt spacing grid; generous padding (16–24)
- No borders on cards, just surface colour contrast

**Motion**
- 200–250 ms ease-out for value changes and sheet transitions
- Curve morphs smoothly when switching presets (interpolate points)
- No bouncy or decorative animation

**Curve view (hero element)**
- Black canvas, faint grid: log frequency lines (20, 50, 100, 200, 500, 1k, 2k, 5k, 10k, 20k) and dB lines every 6 dB, at ~6% white
- 0 dB line slightly brighter
- Composite curve: 2px accent line with a soft glow, gradient fill fading to transparent toward 0 dB
- Each band: a dot in its band colour; selected band shows its individual curve faintly and a Q "handle" ring
- Interactions:
  - Drag dot: horizontal = freq, vertical = gain
  - Scroll / pinch on dot: Q
  - Double-click empty space: add peaking band there
  - Double-click dot: reset gain to 0; right-click: menu (type, disable, delete, solo)
  - Shift-drag: fine adjust
- Range toggle: ±6 / ±12 / ±24 dB

**Layout**
```
┌──────────────────────────────────────────────┐
│  Onyx EQ          [Parametric|Graphic]   ⏻   │  toolbar: mode segmented control, bypass
│  ┌────────────────────────────────────────┐  │
│  │                                        │  │
│  │            CURVE VIEW                  │  │
│  │                                        │  │
│  └────────────────────────────────────────┘  │
│  Preamp  ───●──────  -3.0 dB   [Auto]        │
│  ┌ Band list (horizontal cards) ───────────┐ │
│  │ ● 105 Hz  +4.0 dB  Q 0.7  LowShelf      │ │
│  └─────────────────────────────────────────┘ │
│  Output: Headphones ▾      Preset: Flat ▾    │
└──────────────────────────────────────────────┘
```
- Graphic mode replaces the band cards with vertical sliders (scrollable when many bands), still drawing the resulting smooth curve above.

---

## 5. Phases

### Phase 0 — Spike: prove the audio path (no UI)
- Script that writes a 3-band filter-chain config, launches it, routes audio through it, and changes one band's gain live with `pw-cli`.
- Record the exact working config and `set-param` syntax in `docs/pipewire-notes.md`.
- **Done when:** music plays through "Onyx EQ" sink, and a +12 dB band at 100 Hz audibly changes live with no restart.

### Phase 1 — Core library
- `models.py`, `biquad.py`, `apo.py`, `graphic.py`, `presets.py`.
- APO parser supports: `Preamp:`, `Filter N: ON/OFF PK|LSC|HSC|LP|HP|NO|BP|AP Fc .. Hz Gain .. dB Q ..`, `GraphicEQ:` lines, comments; ignores unsupported directives with a warning list.
- Graphic layouts: ISO 10/15/31 and log-spaced N bands (Q derived from spacing).
- **Done when:** pytest passes for parsing real AutoEQ files, round-trip export, and response curves.

### Phase 2 — Engine
- `chain_config.py` with slot pool; `pipewire.py` (start/stop/restart child, find node id via `pw-dump`, batched `set-param`); `devices.py`.
- Clean shutdown: restore previous default sink on exit.
- **Done when:** a CLI (`python -m onyx_eq.engine --preset file.txt`) applies any APO file and live-edits bands.

### Phase 3 — UI shell + theme
- Window, `Theme.qml`, toolbar, preset menu, output picker, bypass. Pure black, fonts bundled.
- **Done when:** app opens on KDE and GNOME, looks identical, nothing hard-coded outside Theme.

### Phase 4 — Curve editor (parametric mode)
- `CurveView.qml` with all interactions above, band list cards, inspector for exact numeric entry.
- Throttled live updates through the bridge.
- **Done when:** dragging a band is smooth (60 fps UI) and audio follows with no clicks or dropouts.

### Phase 5 — Graphic mode
- Band-count picker (presets + custom N), vertical sliders, same curve view.
- Converting between modes: graphic → parametric keeps bands as peaking filters.
- **Done when:** 127-band graphic EQ is responsive.

### Phase 6 — Polish
- Auto preamp (negative of max boost), clipping warning.
- Undo/redo, A/B compare, keyboard shortcuts.
- Presets: save, rename, import/export APO, drag-and-drop files onto window.
- Per-output-device presets (auto-switch when headphones change).
- Optional "keep EQ running after closing" (systemd user unit).

### Phase 7 — Packaging
- `pyproject.toml` entry point, `.desktop` file, icon.
- AppImage. Then investigate Flatpak (`flatpak-spawn --host` or running the chain inside the sandbox).

---

## 6. Working rules for Claude Code

- Read this file and `docs/pipewire-notes.md` before each phase.
- Keep `core/` pure and tested; write tests before or alongside code.
- Never hard-code colours, fonts or radii outside `Theme.qml`.
- Don't add dependencies without noting why in this file.
- When PipeWire behaviour is uncertain, write a small spike script first and record findings in `docs/pipewire-notes.md`.
- After each phase: run tests, update a short "Status" section at the bottom of this file.

---

## Status
- [x] Phase 0 — 3-band chain + live `set-param` verified by measuring noise through a null sink (`docs/pipewire-notes.md`).
- [x] Phase 1 — core library; biquads match PipeWire within 0.2 dB (measured); AutoEQ parametric/graphic parse + round-trip tested.
- [x] Phase 2 — engine with slot pool, persistent `pw-cli`, devices; `python -m onyx_eq.engine` verified by measurement before/after live edits.
- [x] Phase 3 — QML shell, `Theme.qml` holds every colour/size/duration, Basic style forced so KDE and GNOME look the same.
  Verified offscreen only; not yet looked at on a live GNOME session.
- [x] Phase 4 — curve editor with all §4 interactions, inspector, band cards, 60 Hz coalesced updates.
  Scripted input tests pass; "no clicks while dragging" still needs a listening check.
- [x] Phase 5 — graphic mode: 10/15/31/64/127/custom, paint-drag sliders, least-squares fitting (127-band HD650 fit < 0.5 dB).
  127-band edit + curve redraw ≈ 4.5 ms.
- [x] Phase 6 — auto preamp, clipping badge, undo/redo, A/B, shortcuts, preset save/rename/delete, APO import/export,
  drag-and-drop, per-output presets, keep-running systemd unit (unit install not exercised on this machine).
- [x] Phase 7 (AppImage) — `pyproject.toml` entry points, `.desktop`, icon; `scripts/build-appimage.sh` builds
  `dist/Onyx_EQ-x86_64.AppImage` (~114 MB, CPython 3.12 + PySide6-Essentials). Launch verified offscreen; its engine
  created the chain and linked to the chosen output. Flatpak not started.
  Note: python-appimage passes the desktop `Name=` to appimagetool unquoted, so the script packages the AppDir itself.

Decisions made while building:
- Graphic layouts use bandwidth = 1.5× spacing (ISO 10/15/31) or 2× (log-spaced N), with per-band Q
  pre-warped for the bilinear transform; Q from the spacing alone rippled ±1 dB.
- The displayed curve includes the preamp, as §3.3 specifies.
- Graphic → parametric drops bands at 0 dB so 127 flat peaking filters don't clutter the editor.
