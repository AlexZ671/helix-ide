"""Minimal, dependency-free Discord IPC (Rich Presence) client.

Speaks the local Discord IPC protocol over the unix socket that the Discord
desktop client exposes at $XDG_RUNTIME_DIR/discord-ipc-{0..9}. Only the bits
needed for Rich Presence are implemented: HANDSHAKE + SET_ACTIVITY.

Protocol (each frame): <int32 opcode LE><int32 length LE><utf-8 JSON payload>
Opcodes: 0 HANDSHAKE, 1 FRAME, 2 CLOSE, 3 PING, 4 PONG
"""

import json
import os
import socket
import struct
import time
import uuid

OP_HANDSHAKE = 0
OP_FRAME = 1
OP_CLOSE = 2
OP_PING = 3
OP_PONG = 4


class DiscordRPCError(Exception):
    pass


class DiscordRPC:
    def __init__(self, client_id: str):
        self.client_id = str(client_id)
        self.sock: socket.socket | None = None

    # -- low level ---------------------------------------------------------
    def _ipc_paths(self):
        base = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
        # Discord (and flatpak/snap variants) may place the socket in subdirs.
        roots = [base, os.path.join(base, "app", "com.discordapp.Discord"),
                 os.path.join(base, "snap.discord"), "/tmp"]
        for root in roots:
            for i in range(10):
                yield os.path.join(root, f"discord-ipc-{i}")

    def _send(self, opcode: int, payload: dict):
        if self.sock is None:
            raise DiscordRPCError("not connected")
        data = json.dumps(payload).encode("utf-8")
        header = struct.pack("<ii", opcode, len(data))
        self.sock.sendall(header + data)

    def _recv(self):
        if self.sock is None:
            raise DiscordRPCError("not connected")
        header = self._recv_exact(8)
        opcode, length = struct.unpack("<ii", header)
        data = self._recv_exact(length) if length else b""
        return opcode, json.loads(data.decode("utf-8")) if data else {}

    def _recv_exact(self, n: int) -> bytes:
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise DiscordRPCError("socket closed by Discord")
            buf += chunk
        return buf

    # -- public ------------------------------------------------------------
    def connect(self) -> bool:
        """Find the Discord socket and perform the handshake. Returns success."""
        last_err = None
        for path in self._ipc_paths():
            if not os.path.exists(path):
                continue
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.settimeout(5)
                s.connect(path)
                self.sock = s
                self._send(OP_HANDSHAKE, {"v": 1, "client_id": self.client_id})
                opcode, _ = self._recv()
                if opcode == OP_CLOSE:
                    raise DiscordRPCError("handshake rejected (bad client_id?)")
                self.sock.settimeout(None)
                return True
            except (OSError, DiscordRPCError) as e:
                last_err = e
                self.close()
                continue
        if last_err:
            raise DiscordRPCError(f"could not connect to Discord: {last_err}")
        return False

    def set_activity(self, activity: dict | None):
        """Set (or clear, when activity is None) the Rich Presence."""
        payload = {
            "cmd": "SET_ACTIVITY",
            "args": {"pid": os.getpid(), "activity": activity},
            "nonce": str(uuid.uuid4()),
        }
        self._send(OP_FRAME, payload)
        # Drain the ack so the socket buffer doesn't fill up. Best-effort.
        try:
            self.sock.settimeout(2)
            self._recv()
        except (OSError, DiscordRPCError):
            pass
        finally:
            if self.sock:
                self.sock.settimeout(None)

    def clear(self):
        self.set_activity(None)

    def close(self):
        if self.sock is not None:
            try:
                self.sock.close()
            finally:
                self.sock = None


if __name__ == "__main__":
    # Smoke test: requires a real client_id in HX_PRESENCE_CLIENT_ID.
    cid = os.environ.get("HX_PRESENCE_CLIENT_ID", "")
    if not cid:
        raise SystemExit("set HX_PRESENCE_CLIENT_ID to test")
    rpc = DiscordRPC(cid)
    rpc.connect()
    rpc.set_activity({
        "details": "Testing hx-presence",
        "state": "It works!",
        "timestamps": {"start": int(time.time())},
    })
    print("Activity set; check your Discord profile. Sleeping 15s...")
    time.sleep(15)
    rpc.clear()
    rpc.close()
