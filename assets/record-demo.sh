#!/usr/bin/env bash
# Record the live theme-transition demo GIF for the README.
#
# Wayland (Hyprland) + wf-recorder + slurp + ffmpeg.
# Usage:
#   1. Have the IDE running:  hx   (in a kitty window)
#   2. From a SECOND terminal (a plain kitty, not the IDE), run this script.
#   3. Drag a box over the IDE window when prompted.
#   4. During the countdown's "GO", switch Helix themes a few times:
#         :theme onelight   :theme dark_plus   :theme catppuccin_mocha  ...
#   5. It stops automatically and writes assets/demo.gif.
set -euo pipefail

DUR="${1:-12}"                                   # seconds to record (arg 1)
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUT="$HERE/demo.gif"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

for t in wf-recorder slurp ffmpeg; do
  command -v "$t" >/dev/null || { echo "missing dependency: $t"; exit 1; }
done

echo ":: Select the IDE window/region to record (drag a box over it)..."
GEO="$(slurp)"

echo ":: Recording ${DUR}s — get ready to switch Helix themes."
for i in 3 2 1; do printf '   %s\n' "$i"; sleep 1; done
echo "   GO — :theme onelight / :theme dark_plus / :theme catppuccin_mocha ..."

wf-recorder -g "$GEO" -f "$TMP/rec.mp4" &
REC=$!
sleep "$DUR"
kill -INT "$REC" 2>/dev/null || true
wait "$REC" 2>/dev/null || true

echo ":: Converting to GIF (two-pass palette, 900px, 18fps)..."
ffmpeg -y -i "$TMP/rec.mp4" \
  -vf "fps=18,scale=900:-1:flags=lanczos,palettegen=stats_mode=diff" \
  "$TMP/pal.png" -loglevel error
ffmpeg -y -i "$TMP/rec.mp4" -i "$TMP/pal.png" \
  -lavfi "fps=18,scale=900:-1:flags=lanczos[v];[v][1:v]paletteuse=dither=bayer:bayer_scale=3" \
  "$OUT" -loglevel error

echo ":: Done -> $OUT ($(du -h "$OUT" | cut -f1))"
echo "   Then: git add assets/demo.gif && git commit -m 'docs: add demo gif' && git push"
