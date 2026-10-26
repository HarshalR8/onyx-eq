#!/usr/bin/env bash
# Build dist/Onyx_EQ-x86_64.AppImage with python-appimage (bundles a manylinux CPython, PySide6
# and numpy). Needs network access the first time; output is ~150 MB.
# The AppImage still uses the host's PipeWire tools (pipewire, pw-cli, pw-dump, wpctl).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="${PYTHON_VERSION:-3.12}"
BUILD="$ROOT/build/appimage"
rm -rf "$BUILD" && mkdir -p "$BUILD/recipe" "$ROOT/dist"

"$ROOT/.venv/bin/pip" install -q python-appimage build
"$ROOT/.venv/bin/python" -m build --wheel --outdir "$BUILD/wheel" "$ROOT"
WHEEL="$(ls "$BUILD"/wheel/onyx_eq-*.whl)"

cp "$ROOT/onyx_eq/data/onyx-eq.svg" "$BUILD/recipe/onyx-eq.svg"
sed 's|^Exec=.*|Exec=onyx-eq %F|' "$ROOT/packaging/onyx-eq.desktop" > "$BUILD/recipe/onyx-eq.desktop"
echo "$WHEEL" > "$BUILD/recipe/requirements.txt"
cat > "$BUILD/recipe/entrypoint.sh" <<'SH'
{{ python-executable }} -s -m onyx_eq "$@"
SH

# python-appimage names the output after the desktop Name= ("Onyx EQ") and passes it to
# appimagetool unquoted, which breaks on the space. Build the AppDir only and package it here.
cd "$BUILD"
"$ROOT/.venv/bin/python" -m python_appimage build app --no-packaging -p "$PY" "$BUILD/recipe"
APPDIR="$BUILD/Onyx EQ-$(uname -m)"
TOOL="$("$ROOT/.venv/bin/python" -c 'from python_appimage.utils.deps import ensure_appimagetool; print(ensure_appimagetool())')"
OUT="$ROOT/dist/Onyx_EQ-$(uname -m).AppImage"
ARCH="$(uname -m)" "$TOOL" --no-appstream "$APPDIR" "$OUT"
ls -la "$OUT"
