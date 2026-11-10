"""
Agent (Phase 1).

Runs on the machine you want to view. Captures the screen and streams it,
as JPEG frames, out to the relay server over a WebSocket.

Design commitment baked in: this agent shows a VISIBLE indicator while it is
running and streaming. The person at the machine always knows. That is the
line this project holds to -- consent-based, not covert.

Phase 1 indicator = a clear, always-on-top banner window (tkinter) plus
console logging. Phase 2 adds input forwarding; Phase 4 adds auth + TLS.

Run:  python agent/agent.py --server ws://localhost:8000
"""

import argparse
import asyncio
import io
import json
import random
import socket
import threading
import time
import tkinter as tk
from urllib.parse import urlencode

import mss
import websockets
from PIL import Image
from pynput.keyboard import Controller as KeyboardController
from pynput.keyboard import Key
from pynput.mouse import Button
from pynput.mouse import Controller as MouseController

# ----- tunables -----
FPS = 10                 # frames per second to send
JPEG_QUALITY = 50        # 1-95; lower = smaller/faster
MONITOR_INDEX = 1        # mss: 1 = primary monitor
MAX_WIDTH = 1280         # downscale wide screens to keep bandwidth sane
# --------------------

# ----- build-time defaults (bake these before packaging to .exe) -----
# So a distributed agent knows which relay to call home to, without CLI args.
SERVER_DEFAULT = "ws://localhost:8000"
SECRET_DEFAULT = "dev-secret"          # must match the server's REMOTE_AGENT_SECRET
CODE_DEFAULT = ""                      # fixed 6-digit access code; "" = random each run
# ---------------------------------------------------------------------

# Shared flag so the banner can reflect connection state.
_state = {"connected": False, "frames": 0, "controlling": False,
          "id": "", "code": ""}

# ---- input replay (Phase 2) ----
_mouse = MouseController()
_keyboard = KeyboardController()

_BUTTONS = {"left": Button.left, "right": Button.right, "middle": Button.middle}

# Browser KeyboardEvent.key -> pynput special key. Printable chars pass through.
_SPECIAL_KEYS = {
    "Enter": Key.enter, "Backspace": Key.backspace, "Tab": Key.tab,
    "Escape": Key.esc, "Shift": Key.shift, "Control": Key.ctrl,
    "Alt": Key.alt, "Meta": Key.cmd, "CapsLock": Key.caps_lock,
    "ArrowUp": Key.up, "ArrowDown": Key.down,
    "ArrowLeft": Key.left, "ArrowRight": Key.right,
    "Delete": Key.delete, "Home": Key.home, "End": Key.end,
    "PageUp": Key.page_up, "PageDown": Key.page_down, " ": Key.space,
}


def _to_screen(xn: float, yn: float, mon) -> tuple[int, int]:
    """Normalized (0..1) viewer coords -> absolute screen pixels."""
    x = mon["left"] + xn * mon["width"]
    y = mon["top"] + yn * mon["height"]
    return int(x), int(y)


def _resolve_key(name: str):
    if name in _SPECIAL_KEYS:
        return _SPECIAL_KEYS[name]
    if len(name) == 1:  # a printable character
        return name
    return None  # unknown / ignore


def apply_event(ev: dict, mon) -> None:
    """Replay one input event from the browser on this machine."""
    t = ev.get("t")
    if t in ("move", "down", "up") and "x" in ev:
        _mouse.position = _to_screen(ev["x"], ev["y"], mon)
    if t == "down":
        _mouse.press(_BUTTONS.get(ev.get("button", "left"), Button.left))
    elif t == "up":
        _mouse.release(_BUTTONS.get(ev.get("button", "left"), Button.left))
    elif t == "scroll":
        _mouse.scroll(ev.get("dx", 0), ev.get("dy", 0))
    elif t == "key":
        key = _resolve_key(ev.get("key", ""))
        if key is None:
            return
        if ev.get("pressed"):
            _keyboard.press(key)
        else:
            _keyboard.release(key)


def capture_jpeg(sct, monitor) -> bytes:
    """Grab one frame and return it as JPEG bytes."""
    shot = sct.grab(monitor)
    img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
    if img.width > MAX_WIDTH:
        ratio = MAX_WIDTH / img.width
        img = img.resize((MAX_WIDTH, int(img.height * ratio)))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY)
    return buf.getvalue()


async def send_frames(ws, sct, monitor):
    """Capture + push JPEG frames at the target FPS."""
    frame_interval = 1.0 / FPS
    while True:
        start = time.time()
        await ws.send(capture_jpeg(sct, monitor))
        _state["frames"] += 1
        elapsed = time.time() - start
        await asyncio.sleep(max(0, frame_interval - elapsed))


async def recv_input(ws, monitor):
    """Receive input events (JSON text) from the viewer and replay them."""
    async for msg in ws:
        if isinstance(msg, bytes):
            continue  # agent only receives text events
        try:
            ev = json.loads(msg)
        except Exception:
            continue
        _state["controlling"] = True
        try:
            apply_event(ev, monitor)
        except Exception as e:
            print(f"[agent] input error: {e}")


async def stream(server_url: str, agent_id: str, code: str, secret: str):
    """Connect to the relay; stream frames and accept input (reconnect on drop)."""
    query = urlencode({"id": agent_id, "code": code, "secret": secret})
    ws_url = server_url.rstrip("/") + "/ws/agent?" + query
    while True:
        try:
            print(f"[agent] connecting to {server_url} as id={agent_id} ...")
            async with websockets.connect(ws_url, max_size=None) as ws:
                _state["connected"] = True
                print("[agent] connected -- streaming + accepting input")
                with mss.mss() as sct:
                    monitor = sct.monitors[MONITOR_INDEX]
                    sender = asyncio.create_task(send_frames(ws, sct, monitor))
                    receiver = asyncio.create_task(recv_input(ws, monitor))
                    done, pending = await asyncio.wait(
                        {sender, receiver}, return_when=asyncio.FIRST_COMPLETED
                    )
                    for task in pending:
                        task.cancel()
        except Exception as e:
            print(f"[agent] disconnected ({e}); retrying in 3s")
        finally:
            _state["connected"] = False
            _state["controlling"] = False
        await asyncio.sleep(3)


def run_asyncio(server_url: str, agent_id: str, code: str, secret: str):
    asyncio.run(stream(server_url, agent_id, code, secret))


def run_banner():
    """Always-on-top window so the host can SEE the session is live."""
    root = tk.Tk()
    root.title("Remote session")
    root.attributes("-topmost", True)
    root.geometry("300x64+20+20")
    root.configure(bg="#b00020")

    label = tk.Label(
        root,
        text="",
        fg="white",
        bg="#b00020",
        font=("Helvetica", 12, "bold"),
        justify="left",
    )
    label.pack(expand=True, fill="both", padx=10, pady=10)

    def tick():
        ident = f"id {_state['id']} · code {_state['code']}"
        if _state["connected"]:
            verb = "BEING CONTROLLED" if _state["controlling"] else "SESSION ACTIVE"
            label.config(text=f"🔴 REMOTE {verb}\n{ident}")
        else:
            label.config(text=f"⚪ Remote agent running (not connected)\n{ident}")
        root.after(500, tick)

    tick()
    root.mainloop()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", default=SERVER_DEFAULT,
                        help="relay server, e.g. ws://1.2.3.4:8000 or wss://host")
    parser.add_argument("--secret", default=SECRET_DEFAULT,
                        help="shared secret (must match server REMOTE_AGENT_SECRET)")
    parser.add_argument("--id", default="",
                        help="agent id (default: hostname-xxxx)")
    parser.add_argument("--code", default="",
                        help="access code a viewer must enter "
                             "(default: CODE_DEFAULT if set, else random 6-digit)")
    parser.add_argument("--no-banner", action="store_true",
                        help="disable the GUI banner (console indicator still prints)")
    args = parser.parse_args()

    agent_id = args.id or f"{socket.gethostname().split('.')[0]}-{random.randint(1000, 9999)}"
    code = args.code or CODE_DEFAULT or f"{random.randint(0, 999999):06d}"
    _state["id"] = agent_id
    _state["code"] = code

    print("=" * 48)
    print(f" agent id   : {agent_id}")
    print(f" access code: {code}   <- give this to the viewer")
    print(f" server     : {args.server}")
    print("=" * 48)

    # asyncio streaming runs in a background thread; tkinter owns the main thread.
    t = threading.Thread(
        target=run_asyncio,
        args=(args.server, agent_id, code, args.secret),
        daemon=True,
    )
    t.start()

    if args.no_banner:
        t.join()
    else:
        run_banner()


if __name__ == "__main__":
    main()
