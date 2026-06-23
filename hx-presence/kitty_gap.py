#!/usr/bin/env python3
"""Recolour the kitty window background (the margin/gap around the panes).

This runs OUTSIDE zellij — in the kitty shell that launched the IDE — because
OSC 11 only reaches the real kitty window from its own tty; inside a zellij pane
zellij swallows it. It watches ``theme-state`` (written by theme_sync.py in the
editor pane) and fades the window background to the new theme colour.

Started and killed by the ``hx`` fish function around the zellij session.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from theme_sync import STATE, STEPS, DURATION, _hex2rgb, _rgb2hex, _lerp  # noqa: E402


def osc_bg(hexcolor):
    # OSC 11 = set default background; written in one syscall so it can't
    # interleave with zellij's output on the shared tty.
    try:
        os.write(1, ("\033]11;%s\a" % hexcolor).encode())
    except OSError:
        pass


def read_target():
    try:
        parts = open(STATE).read().split()
    except OSError:
        return None
    return parts[0] if parts else None


def animate(old, new):
    o, n = _hex2rgb(old), _hex2rgb(new)
    for i in range(1, STEPS + 1):
        osc_bg(_rgb2hex(_lerp(o, n, i / STEPS)))
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
                    osc_bg(target)          # snap on first sight
                else:
                    animate(current, target)
                current = target
        time.sleep(0.2)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, BrokenPipeError):
        pass
