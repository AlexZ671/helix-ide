#!/usr/bin/env python3
"""Transparent PTY wrapper around Helix that publishes Discord Rich Presence.

It runs the real `hx` inside a pseudo-terminal, forwards all I/O unchanged, and
in parallel feeds the output through a terminal emulator (pyte) to read the
currently focused file out of Helix's statusline. The editor experience is
untouched; if Discord is closed or unconfigured the wrapper is a no-op proxy.

Usage:  hx_presence.py <helix-command> [args...]
e.g.    hx_presence.py /usr/local/bin/hx src/main.rs
"""

import fcntl
import json
import os
import pty
import re
import select
import signal
import struct
import sys
import termios
import threading
import time
import tty

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pyte  # noqa: E402
from languages import resolve, HELIX_LOGO  # noqa: E402
from discord_rpc import DiscordRPC, DiscordRPCError  # noqa: E402
from theme_sync import ThemeSync, sample_colors  # noqa: E402

THEME_SAMPLE_INTERVAL = 0.25  # seconds between palette samples (CPU-friendly)

HERE = os.path.dirname(os.path.abspath(__file__))
LOGFILE = os.path.join(HERE, "presence.log")
MODE_TOKENS = {"NOR", "INS", "SEL", "INSERT", "NORMAL", "SELECT"}
MOD_INDICATORS = {"[+]", "[-]", "[*]", "[+", "+]"}


def log(msg):
    if os.environ.get("HX_PRESENCE_DEBUG") != "1":
        return
    try:
        with open(LOGFILE, "a") as f:
            f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
    except OSError:
        pass


def load_config():
    cfg = {"client_id": "", "show_idle": True}
    path = os.path.join(HERE, "config.json")
    try:
        with open(path) as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass
    env_id = os.environ.get("HX_PRESENCE_CLIENT_ID")
    if env_id:
        cfg["client_id"] = env_id
    return cfg


# --------------------------------------------------------------------------
# Window size helpers
# --------------------------------------------------------------------------
def get_winsize(fd):
    try:
        s = fcntl.ioctl(fd, termios.TIOCGWINSZ, b"\0" * 8)
        rows, cols, _, _ = struct.unpack("HHHH", s)
        if rows and cols:
            return rows, cols
    except OSError:
        pass
    return 40, 120


def set_winsize(fd, rows, cols):
    try:
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
    except OSError:
        pass


# --------------------------------------------------------------------------
# Statusline parsing
# --------------------------------------------------------------------------
def parse_statusline(display_rows):
    """Return (filename_or_None, file_type_or_None) read from Helix's
    statusline. Returns (None, None) when nothing parseable was found so the
    caller can keep the previous state."""
    # Scan bottom-up for the row whose first token is a Helix mode indicator.
    for row in reversed(display_rows):
        text = row.rstrip()
        stripped = text.lstrip()
        if not stripped:
            continue
        first = stripped.split(None, 1)
        if first[0] not in MODE_TOKENS:
            continue
        rest = first[1] if len(first) > 1 else ""
        # Left section (file) is separated from center/right by 2+ spaces.
        chunks = [c for c in re.split(r"\s{2,}", rest) if c.strip()]
        if not chunks:
            return None, None
        file_region = chunks[0].strip()
        file_type = None
        # Right-most chunk is the file-type when the statusline exposes it.
        last = chunks[-1].strip().lower()
        if re.fullmatch(r"[a-z][a-z0-9+\-]*", last) and last not in ("lf", "crlf", "cr"):
            file_type = last

        tokens = file_region.split()
        # Drop a leading spinner glyph (single non-ascii char).
        if tokens and len(tokens[0]) == 1 and ord(tokens[0]) > 0x2500:
            tokens = tokens[1:]
        # Drop trailing modification indicators.
        while tokens and tokens[-1] in MOD_INDICATORS:
            tokens = tokens[:-1]
        if not tokens:
            return None, None
        filename = " ".join(tokens)
        if filename.startswith("[") and filename.endswith("]"):
            return None, file_type  # scratch / no real file
        return filename, file_type
    return None, None


# --------------------------------------------------------------------------
# Presence updater (background thread, fully best-effort)
# --------------------------------------------------------------------------
class PresenceUpdater(threading.Thread):
    MIN_INTERVAL = 4.0  # seconds between Discord updates (rate-limit safe)
    RECONNECT_EVERY = 30.0

    def __init__(self, cfg):
        super().__init__(daemon=True)
        self.cfg = cfg
        self.rpc = None
        self.start_ts = int(time.time())
        self._lock = threading.Lock()
        self._desired = (None, None)  # (filename, file_type)
        self._sent = object()         # sentinel != any real value
        self._last_push = 0.0
        self._last_connect_try = 0.0
        self._running = True

    def update(self, filename, file_type):
        if filename is None and file_type is None:
            return  # unparseable frame, keep previous
        with self._lock:
            if (filename, file_type) != self._desired:
                log(f"detected: file={filename!r} type={file_type!r}")
            self._desired = (filename, file_type)

    def _ensure_connection(self):
        if self.rpc is not None:
            return True
        if not self.cfg.get("client_id"):
            return False
        now = time.time()
        if now - self._last_connect_try < self.RECONNECT_EVERY:
            return False
        self._last_connect_try = now
        try:
            rpc = DiscordRPC(self.cfg["client_id"])
            if rpc.connect():
                self.rpc = rpc
                log("connected to Discord")
                return True
        except DiscordRPCError as e:
            log(f"connect failed: {e}")
        return False

    def _build_activity(self, filename, file_type):
        if filename is None:
            if not self.cfg.get("show_idle", True):
                return None
            return {
                "details": "Idle",
                "state": "In Helix",
                "timestamps": {"start": self.start_ts},
                "assets": {"large_image": HELIX_LOGO, "large_text": "Helix editor"},
            }
        label, icon_url = resolve(filename, file_type)
        return {
            "details": f"Editing {os.path.basename(filename)}"[:128],
            "state": label[:128],
            "timestamps": {"start": self.start_ts},
            "assets": {
                "large_image": icon_url, "large_text": label,
                "small_image": HELIX_LOGO, "small_text": "Helix editor",
            },
        }

    def run(self):
        while self._running:
            time.sleep(1.0)
            with self._lock:
                desired = self._desired
            if desired == self._sent:
                continue
            if time.time() - self._last_push < self.MIN_INTERVAL:
                continue
            if not self._ensure_connection():
                continue
            try:
                self.rpc.set_activity(self._build_activity(*desired))
                self._sent = desired
                self._last_push = time.time()
                log(f"pushed activity: {desired}")
            except (DiscordRPCError, OSError) as e:
                log(f"push failed, dropping connection: {e}")
                try:
                    self.rpc.close()
                except Exception:
                    pass
                self.rpc = None

    def stop(self):
        self._running = False
        if self.rpc is not None:
            try:
                self.rpc.clear()
                self.rpc.close()
            except Exception:
                pass


# --------------------------------------------------------------------------
# Main PTY loop
# --------------------------------------------------------------------------
def main():
    if len(sys.argv) < 2:
        sys.stderr.write("usage: hx_presence.py <helix-command> [args...]\n")
        return 2
    cmd = sys.argv[1:]
    cfg = load_config()

    rows, cols = get_winsize(sys.stdout.fileno())
    screen = pyte.Screen(cols, rows)
    stream = pyte.ByteStream(screen)

    updater = PresenceUpdater(cfg)
    updater.start()

    themesync = ThemeSync()
    themesync.start()
    last_sample = 0.0

    pid, master = pty.fork()
    if pid == 0:
        try:
            os.execvp(cmd[0], cmd)
        except OSError as e:
            sys.stderr.write(f"hx-presence: cannot run {cmd[0]}: {e}\n")
        os._exit(127)

    set_winsize(master, rows, cols)

    stdin_fd = sys.stdin.fileno()
    old_attr = None
    if os.isatty(stdin_fd):
        try:
            old_attr = termios.tcgetattr(stdin_fd)
            tty.setraw(stdin_fd)
        except termios.error:
            old_attr = None

    def on_winch(_sig, _frm):
        r, c = get_winsize(sys.stdout.fileno())
        set_winsize(master, r, c)
        try:
            screen.resize(r, c)
        except Exception:
            pass

    signal.signal(signal.SIGWINCH, on_winch)

    status = 0
    try:
        while True:
            try:
                rlist, _, _ = select.select([stdin_fd, master], [], [], 0.2)
            except InterruptedError:
                continue
            if master in rlist:
                try:
                    data = os.read(master, 65536)
                except OSError:
                    break
                if not data:
                    break
                os.write(sys.stdout.fileno(), data)
                try:
                    stream.feed(data)
                    fname, ftype = parse_statusline(screen.display)
                    updater.update(fname, ftype)
                    now = time.time()
                    if now - last_sample >= THEME_SAMPLE_INTERVAL:
                        last_sample = now
                        themesync.update(sample_colors(screen))
                except Exception as e:  # parsing must never break the editor
                    log(f"parse error: {e}")
            if stdin_fd in rlist:
                try:
                    data = os.read(stdin_fd, 65536)
                except OSError:
                    data = b""
                if data:
                    os.write(master, data)
    finally:
        if old_attr is not None:
            termios.tcsetattr(stdin_fd, termios.TCSADRAIN, old_attr)
        updater.stop()
        themesync.stop()
        try:
            _, status = os.waitpid(pid, 0)
        except OSError:
            status = 0

    return os.waitstatus_to_exitcode(status)


if __name__ == "__main__":
    sys.exit(main())
