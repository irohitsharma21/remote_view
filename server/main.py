"""
Relay server (Phase 3 + 4).

Phase 3 — multi-agent:
  - many agents can register, each under its own id
  - viewers pick an agent; frames and input are routed per-agent

Phase 4 — auth:
  - AGENTS must present a shared secret to register (stops strangers
    registering machines to your relay)
  - each agent generates a 6-digit ACCESS CODE shown in its banner; a viewer
    must supply that code to connect (TeamViewer-style "ID + password")
  - ADMIN must log in with a password to use the dashboard / connect at all

Env vars (all optional; sensible dev defaults, printed at startup):
  REMOTE_ADMIN_PASSWORD   password for the web dashboard
  REMOTE_AGENT_SECRET     shared secret agents must send to register

Run (plain):
  uvicorn server.main:app --host 0.0.0.0 --port 8000
Run (TLS, see scripts/gen_cert.sh):
  uvicorn server.main:app --host 0.0.0.0 --port 8443 \
      --ssl-keyfile certs/key.pem --ssl-certfile certs/cert.pem
"""

from __future__ import annotations

import os
import secrets
import time
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="remote_control relay")
WEB_DIR = Path(__file__).resolve().parent.parent / "web"

# ---- config / secrets ----
ADMIN_PASSWORD = os.environ.get("REMOTE_ADMIN_PASSWORD") or secrets.token_hex(4)
AGENT_SECRET = os.environ.get("REMOTE_AGENT_SECRET") or "dev-secret"
_GENERATED_PW = "REMOTE_ADMIN_PASSWORD" not in os.environ

# ---- in-memory state ----
# agent_id -> {ws, code, latest_frame, viewers:set, since}
agents: dict[str, dict] = {}
# valid admin session tokens (reset on restart)
tokens: set[str] = set()


def _check_token(token: str | None) -> bool:
    return bool(token) and token in tokens


# ======================= auth (HTTP) =======================

@app.post("/api/login")
async def login(req: Request):
    body = await req.json()
    if secrets.compare_digest(str(body.get("password", "")), ADMIN_PASSWORD):
        token = secrets.token_urlsafe(24)
        tokens.add(token)
        return {"token": token}
    return JSONResponse({"error": "bad password"}, status_code=401)


@app.get("/api/agents")
async def list_agents(token: str = ""):
    if not _check_token(token):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    now = time.time()
    return [
        {"id": aid, "viewers": len(a["viewers"]), "uptime": int(now - a["since"])}
        for aid, a in agents.items()
    ]


# ======================= agent socket =======================

@app.websocket("/ws/agent")
async def ws_agent(ws: WebSocket, id: str = "", code: str = "", secret: str = ""):
    # Authenticate the agent before accepting.
    if not secrets.compare_digest(secret, AGENT_SECRET):
        await ws.close(code=1008)
        print(f"[server] agent '{id}' rejected (bad secret)")
        return
    if not id:
        await ws.close(code=1008)
        return

    await ws.accept()
    agents[id] = {
        "ws": ws, "code": code, "latest_frame": None,
        "viewers": set(), "since": time.time(),
    }
    print(f"[server] agent '{id}' connected (code {code})")
    try:
        while True:
            frame = await ws.receive_bytes()
            entry = agents.get(id)
            if entry is None:
                break
            entry["latest_frame"] = frame
            dead = []
            for v in entry["viewers"]:
                try:
                    await v.send_bytes(frame)
                except Exception:
                    dead.append(v)
            for v in dead:
                entry["viewers"].discard(v)
    except WebSocketDisconnect:
        print(f"[server] agent '{id}' disconnected")
    except Exception as e:
        print(f"[server] agent '{id}' error: {e}")
    finally:
        agents.pop(id, None)


# ======================= viewer socket =======================

@app.websocket("/ws/viewer/{agent_id}")
async def ws_viewer(ws: WebSocket, agent_id: str, token: str = "", code: str = ""):
    # Accept first, then validate -- so the browser receives a real close code
    # (1008 = bad token/code, 1011 = agent gone) it can show to the user.
    await ws.accept()
    if not _check_token(token):
        await ws.close(code=1008)
        return
    entry = agents.get(agent_id)
    if entry is None:
        await ws.close(code=1011)  # agent not connected
        return
    if not secrets.compare_digest(code, entry["code"]):
        await ws.close(code=1008)  # wrong access code
        print(f"[server] viewer rejected for '{agent_id}' (bad code)")
        return

    entry["viewers"].add(ws)
    print(f"[server] viewer connected to '{agent_id}' ({len(entry['viewers'])})")
    if entry["latest_frame"] is not None:
        await ws.send_bytes(entry["latest_frame"])
    try:
        while True:
            msg = await ws.receive_text()  # input events -> forward to agent
            agent = agents.get(agent_id)
            if agent is not None:
                try:
                    await agent["ws"].send_text(msg)
                except Exception:
                    pass
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        entry["viewers"].discard(ws)


# ======================= pages =======================

@app.get("/")
async def dashboard():
    return FileResponse(WEB_DIR / "dashboard.html")


@app.get("/viewer")
async def viewer():
    return FileResponse(WEB_DIR / "viewer.html")


app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


@app.on_event("startup")
async def _startup():
    print("=" * 56)
    print(" remote_control relay")
    if _GENERATED_PW:
        print(f"  ADMIN PASSWORD (generated): {ADMIN_PASSWORD}")
        print("  -> set REMOTE_ADMIN_PASSWORD to choose your own")
    else:
        print("  ADMIN PASSWORD: (from REMOTE_ADMIN_PASSWORD)")
    print(f"  AGENT SECRET: {AGENT_SECRET}")
    print("=" * 56)
