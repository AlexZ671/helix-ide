#!/usr/bin/env python3
"""Runs inside the bottom terminal pane of the Helix IDE layout.

Watches ``theme-state`` (written by theme_sync.py in the editor pane) and, when
the target colours change, animates *this* pane to match — so the terminal
fades in step with the editor when you switch Helix themes.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from theme_sync import (  # noqa: E402
    STATE, STEPS, DURATION, _hex2rgb, _rgb2hex, _lerp, set_pane_color,
)


def read_target():
    try:
        parts = open(STATE).read().split()
    except OSError:
        return None
    if not parts:
        return None
    bg = parts[0]
    fg = parts[1] if len(parts) > 1 else None
    return bg, fg


def animate(old, new):
    obg, nbg = _hex2rgb(old[0]), _hex2rgb(new[0])
    fade_fg = bool(old[1] and new[1])
    ofg = _hex2rgb(old[1]) if fade_fg else None
    nfg = _hex2rgb(new[1]) if fade_fg else None
    for i in range(1, STEPS + 1):
        t = i / STEPS
        bg = _rgb2hex(_lerp(obg, nbg, t))
        fg = _rgb2hex(_lerp(ofg, nfg, t)) if fade_fg else new[1]
        set_pane_color(bg, fg)            # no pane-id => this pane
        time.sleep(DURATION / STEPS)


def main():
    current = None
    last_mtime = 0.0
    while True:
        try:
            mtime = os.path.getmtime(STATE)
        except OSError:
            mtime = 0.0
        if mtime and mtime != last_mtime:
            last_mtime = mtime
            target = read_target()
            if target and target != current:
                if current is None:
                    set_pane_color(target[0], target[1])   # snap on first sight
                else:
                    animate(current, target)
                current = target
        time.sleep(0.2)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
