#!/usr/bin/env bash
# Run Onyx EQ from this checkout via your app menu: installs a launcher, desktop entry and icon
# into ~/.local. Undo with: scripts/install-desktop.sh --uninstall
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="$HOME/.local/bin/onyx-eq"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICONS="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"

if [[ "${1:-}" == "--uninstall" ]]; then
    rm -f "$BIN" "$APPS/onyx-eq.desktop" "$ICONS/onyx-eq.svg"
    echo "Removed Onyx EQ launcher."
    exit 0
fi

if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
    python3 -m venv "$ROOT/.venv"
    "$ROOT/.venv/bin/pip" install -q -e "$ROOT[dev]"
fi
mkdir -p "$(dirname "$BIN")" "$APPS" "$ICONS"
cat > "$BIN" <<SH
#!/usr/bin/env bash
cd "$ROOT" && exec "$ROOT/.venv/bin/python" -m onyx_eq "\$@"
SH
chmod +x "$BIN"
cp "$ROOT/onyx_eq/data/onyx-eq.svg" "$ICONS/onyx-eq.svg"
sed "s|^Exec=.*|Exec=$BIN %F|" "$ROOT/packaging/onyx-eq.desktop" > "$APPS/onyx-eq.desktop"
command -v update-desktop-database >/dev/null && update-desktop-database "$APPS" || true
echo "Installed: $BIN and $APPS/onyx-eq.desktop"
