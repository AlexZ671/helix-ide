#!/usr/bin/env bash
# Helix IDE rice — installer.
# Copies configs into ~/.config, sets up the hx-presence Python venv, and backs
# up anything it overwrites to <file>.bak-<timestamp>.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}"
SHARE="${XDG_DATA_HOME:-$HOME/.local/share}"
PRESENCE="$SHARE/hx-presence"
STAMP="$(date +%Y%m%d-%H%M%S)"

say()  { printf '\033[1;36m::\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$*"; }

# Install one file, backing up the destination if it already exists.
install_file() {
  local src="$REPO/$1" dst="$2"
  mkdir -p "$(dirname "$dst")"
  if [ -e "$dst" ] && [ ! -L "$dst" ]; then
    mv "$dst" "$dst.bak-$STAMP"
    warn "backed up $dst -> $dst.bak-$STAMP"
  fi
  cp "$src" "$dst"
  echo "   -> $dst"
}

# ---------------------------------------------------------------- deps
say "Checking dependencies (warnings only)..."
if command -v hx >/dev/null 2>&1 || command -v helix >/dev/null 2>&1; then
  echo "   ok  helix"
else
  warn "missing: helix  (install Helix — the binary is 'hx' or 'helix')"
fi
for tool in zellij kitty fish python3; do
  command -v "$tool" >/dev/null 2>&1 && echo "   ok  $tool" || warn "missing: $tool"
done
command -v starship >/dev/null 2>&1 && echo "   ok  starship" || warn "optional: starship (IDE prompt)"

# ---------------------------------------------------------------- configs
say "Installing configs into $CONFIG ..."
install_file config/helix/config.toml            "$CONFIG/helix/config.toml"
install_file config/helix/languages.toml         "$CONFIG/helix/languages.toml"
for t in "$REPO"/config/helix/themes/*.toml; do
  [ -e "$t" ] || continue
  install_file "config/helix/themes/$(basename "$t")" "$CONFIG/helix/themes/$(basename "$t")"
done
install_file config/zellij/config.kdl            "$CONFIG/zellij/config.kdl"
install_file config/zellij/layouts/hx-ide.kdl    "$CONFIG/zellij/layouts/hx-ide.kdl"
install_file config/kitty/kitty.conf             "$CONFIG/kitty/kitty.conf"
install_file config/kitty/theme.conf             "$CONFIG/kitty/theme.conf"
install_file config/kitty/search.py              "$CONFIG/kitty/search.py"
install_file config/kitty/scroll_mark.py         "$CONFIG/kitty/scroll_mark.py"
install_file config/fish/functions/hx.fish       "$CONFIG/fish/functions/hx.fish"
install_file config/starship-ide.toml            "$CONFIG/starship-ide.toml"

# ---------------------------------------------------------------- hx-presence
say "Installing hx-presence into $PRESENCE ..."
mkdir -p "$PRESENCE"
cp "$REPO/hx-presence/"*.py "$PRESENCE/"
echo "   -> $PRESENCE/*.py"
if [ ! -f "$PRESENCE/config.json" ]; then
  cp "$REPO/hx-presence/config.example.json" "$PRESENCE/config.json"
  echo "   -> $PRESENCE/config.json (from template; edit to enable Discord presence)"
fi

# ---------------------------------------------------------------- venv
if command -v python3 >/dev/null 2>&1; then
  say "Creating Python venv for the theme-sync / presence wrapper ..."
  python3 -m venv "$PRESENCE/venv"
  "$PRESENCE/venv/bin/pip" install -q --upgrade pip
  "$PRESENCE/venv/bin/pip" install -q -r "$REPO/hx-presence/requirements.txt"
  echo "   -> $PRESENCE/venv ($(grep -c . "$REPO/hx-presence/requirements.txt") packages)"
else
  warn "python3 not found — skipping venv. Theme sync & presence won't run until you create it."
fi

cat <<EOF

$(say "Done.")
Next steps:
  1. Restart kitty completely (so allow_remote_control / listen_on take effect).
  2. Run:  hx
  3. In Helix, switch theme with  :theme <name>  — the whole IDE fades to match.

Notes:
  • Discord Rich Presence is off by default. To enable it, put a client_id in
    $PRESENCE/config.json (see README "Discord presence").
  • Your previous configs were saved as *.bak-$STAMP next to each file.
EOF
