#!/usr/bin/env python3
"""Live theme synchronisation for the Helix IDE layout.

Helix has no hook that fires on `:theme`, so we detect a theme change the only
place it is observable: the colours Helix actually paints. ``hx_presence.py``
already feeds Helix's output through a pyte screen; here we sample the modal
background/foreground of the editor area, and when it changes we animate every
other surface of the IDE to match:

  * the editor zellij pane (its default colour + frame)   -> driven here
  * the kitty window / inter-pane gap                      -> driven here
  * the bottom terminal pane                               -> driven by
    ``theme_watch.py`` running inside that pane, which reads ``theme-state``.

Everything is best-effort: if zellij/kitty calls fail the editor is untouched.
"""

import os
import subprocess
import threading
import time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "theme-state")
LOGFILE = os.path.join(HERE, "presence.log")

STEPS = 8          # interpolation steps per transition
DURATION = 0.30    # seconds per transition
STABILITY = 0.35   # colour must hold this long before we animate (anti-flicker)

_HEXDIGITS = set("0123456789abcdefABCDEF")
_DEBUG = os.environ.get("HX_PRESENCE_DEBUG") == "1"


def _log(msg):
    if not _DEBUG:
        return
    try:
        with open(LOGFILE, "a") as f:
            f.write("%s [sync] %s\n" % (time.strftime("%H:%M:%S"), msg))
    except OSError:
        pass


# --------------------------------------------------------------------------
# Colour helpers
# --------------------------------------------------------------------------
def _is_hex6(s):
    return isinstance(s, str) and len(s) == 6 and all(c in _HEXDIGITS for c in s)


def _hex2rgb(h):
    h = h.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _rgb2hex(rgb):
    return "#%02X%02X%02X" % rgb


def _lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _run(args):
    try:
        r = subprocess.run(args, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=2)
        if r.returncode != 0:
            _log("FAILED rc=%d: %s | %s" % (
                r.returncode, " ".join(args[:6]),
                r.stdout.decode("utf-8", "replace").strip()[:120]))
            return False
        return True
    except Exception as e:
        _log("EXC %s: %s" % (args[1] if len(args) > 1 else args[0], e))
        return False


def set_pane_color(bg, fg=None, pane_id=None):
    """Set a zellij pane's default colours (recolours background + frame).
    With ``pane_id=None`` zellij targets $ZELLIJ_PANE_ID (the caller's pane)."""
    args = ["zellij", "action", "set-pane-color", "--bg", bg]
    if pane_id:
        args[3:3] = ["--pane-id", pane_id]
    if fg:
        args += ["--fg", fg]
    _run(args)


# --------------------------------------------------------------------------
# Sampling Helix's current palette out of the pyte screen
# --------------------------------------------------------------------------
def sample_colors(screen):
    """Return ``(bg_hex, fg_hex_or_None)`` for the dominant editor colours, or
    ``None`` when nothing usable was painted (e.g. a transparent-bg theme)."""
    bgc, fgc = Counter(), Counter()
    buf = screen.buffer
    # Skip the last row (statusline) so its accent colours don't win the vote.
    for y in range(max(0, screen.lines - 1)):
        row = buf.get(y)
        if not row:
            continue
        for ch in row.values():
            if _is_hex6(ch.bg):
                bgc[ch.bg] += 1
            if _is_hex6(ch.fg):
                fgc[ch.fg] += 1
    if not bgc:
        _maybe_log_votes(None, bgc, fgc)
        return None
    bg = "#" + bgc.most_common(1)[0][0].upper()
    fg = "#" + fgc.most_common(1)[0][0].upper() if fgc else None
    _maybe_log_votes((bg, fg), bgc, fgc)
    return bg, fg


_last_logged_winner = object()


def _maybe_log_votes(winner, bgc, fgc):
    """When debugging, log the colour vote breakdown — but only when the winning
    colour changes, so the log isn't spammed every sample."""
    global _last_logged_winner
    if not _DEBUG or winner == _last_logged_winner:
        return
    _last_logged_winner = winner
    top = lambda c: ", ".join("#%s x%d" % (k, n) for k, n in c.most_common(4))
    _log("sample -> %s | bg{%s} | fg{%s}" % (winner, top(bgc), top(fgc)))


# --------------------------------------------------------------------------
# Animated synchroniser (background thread)
# --------------------------------------------------------------------------
class ThemeSync(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.pane = os.environ.get("ZELLIJ_PANE_ID")
        self._lock = threading.Lock()
        self._desired = None
        self._pending_since = 0.0
        self._current = None
        self._running = True

    def update(self, colors):
        if not colors:
            return
        with self._lock:
            if colors != self._desired:
                self._desired = colors
                self._pending_since = time.time()

    def _publish(self, colors):
        try:
            with open(STATE, "w") as f:
                f.write("%s %s\n" % (colors[0], colors[1] or ""))
        except OSError:
            pass

    def _apply(self, bg, fg):
        # Editor pane + its frame. The kitty window background (the gap/margin)
        # is handled out-of-band by kitty_gap.py via OSC 11, since `kitty @`
        # needs remote control and OSC doesn't survive a zellij pane.
        if self.pane:
            set_pane_color(bg, fg, self.pane)

    def _animate(self, old, new):
        obg, nbg = _hex2rgb(old[0]), _hex2rgb(new[0])
        fade_fg = bool(old[1] and new[1])
        ofg = _hex2rgb(old[1]) if fade_fg else None
        nfg = _hex2rgb(new[1]) if fade_fg else None
        for i in range(1, STEPS + 1):
            t = i / STEPS
            bg = _rgb2hex(_lerp(obg, nbg, t))
            fg = _rgb2hex(_lerp(ofg, nfg, t)) if fade_fg else new[1]
            self._apply(bg, fg)
            time.sleep(DURATION / STEPS)

    def run(self):
        while self._running:
            time.sleep(0.1)
            with self._lock:
                desired, since = self._desired, self._pending_since
            if desired is None or desired == self._current:
                continue
            if time.time() - since < STABILITY:
                continue
            old, self._current = self._current, desired
            _log("transition %s -> %s (pane=%s)" % (old, desired, self.pane))
            self._publish(desired)               # let the terminal pane start fading
            if old is None:
                self._apply(*desired)            # first paint — snap, no animation
            else:
                self._animate(old, desired)

    def stop(self):
        self._running = False
