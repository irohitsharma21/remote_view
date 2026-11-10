# remote_control

A consent-based remote-desktop tool (like RustDesk / TeamViewer unattended mode).
The agent connects **outbound** to a relay server, and you view/control it from a
web dashboard — so it works across the internet without opening firewall ports.

**Design rule:** the agent always shows a visible "remote session active" banner
with its ID and access code. It is not built to hide from the person at the machine.

## Layout

```
agent/agent.py     # runs on the host: captures screen, replays input, shows banner
server/main.py     # relay + auth: routes frames/input per-agent, serves the web UI
web/dashboard.html # admin: log in, see connected machines
web/viewer.html    # view + control one machine (needs its access code)
scripts/           # TLS cert + .exe build helpers
```

## How it fits together

```
 [Host PC]                      [Your relay server]                [You, browser]
 agent.exe  ──ws/wss (outbound)──▶  authenticates agents    ◀──── dashboard + viewer
   │  id + access code                routes per agent id          (admin password
   │  shows red banner                                              + agent's code)
   └─ screen frames ─▶ relay ─▶ viewer ;  viewer input ─▶ relay ─▶ agent replays
```

**Two secrets, two roles:**
- **Admin password** (`REMOTE_ADMIN_PASSWORD`) — you, to log into the dashboard.
- **Agent secret** (`REMOTE_AGENT_SECRET`) — shared, lets an agent register to your
  relay (keeps strangers from registering machines).
- **Per-agent access code** — a 6-digit code each agent shows on its banner; whoever
  views that machine must type it. This is the "password to access that computer."

## Setup

```bash
cd /Users/rohitsharma21/Developer/remote_control
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run (local)

**Server:**
```bash
REMOTE_ADMIN_PASSWORD=choose-me REMOTE_AGENT_SECRET=shared-secret \
  uvicorn server.main:app --host 0.0.0.0 --port 8000
```
(If you don't set `REMOTE_ADMIN_PASSWORD`, the server prints a random one at startup.)

**Agent:**
```bash
python agent/agent.py --server ws://localhost:8000 --secret shared-secret
```
It prints and displays an **access code** on its banner.

**You:** open <http://localhost:8000>, log in with the admin password, click the
machine, enter its access code → you see and (tick "send my input") control it.

### macOS permissions (host side)
- **Screen Recording** — to capture the screen (Phase 1)
- **Accessibility** — to replay mouse/keyboard (Phase 2)
Both: System Settings → Privacy & Security → grant your terminal / the agent app.

## Run over the internet
1. Put this repo on a VPS with a public IP; run the **server** there.
2. Add TLS (don't send passwords in clear):
   ```bash
   bash scripts/gen_cert.sh        # self-signed, for testing
   uvicorn server.main:app --host 0.0.0.0 --port 8443 \
       --ssl-keyfile certs/key.pem --ssl-certfile certs/cert.pem
   ```
   For production use a real cert (Caddy or nginx + Let's Encrypt in front).
3. Point agents at it: `python agent/agent.py --server wss://your-host:8443 --secret ...`

## Package the agent to a single executable
Edit the bake-in defaults at the top of [agent/agent.py](agent/agent.py) first:
```python
SERVER_DEFAULT = "wss://your-relay.example.com"
SECRET_DEFAULT = "your-shared-secret"
```
Then:
- **macOS / Linux:** `bash scripts/build_agent.sh` → `dist/remote_agent`
- **Windows (.exe):** run `scripts\build_agent.bat` **on a Windows machine** →
  `dist\remote_agent.exe`

> PyInstaller builds for the OS it runs on — a Windows `.exe` must be built on Windows
> (or via a Windows CI runner / VM). The person who runs it still sees the banner.

## Status
- ✅ Phase 1 — live screen streaming
- ✅ Phase 2 — mouse/keyboard control
- ✅ Phase 3 — multi-agent relay + dashboard (agent IDs)
- ✅ Phase 4 — admin login, agent secret, per-agent access code, TLS, `.exe` packaging

## Notes / next ideas
- Tokens live in memory (reset on server restart). A real deployment would persist
  them (JWT or a store) and add rate-limiting on `/api/login`.
- Latency/quality: tune `FPS`, `JPEG_QUALITY`, `MAX_WIDTH` in `agent/agent.py`.
  A production tool would move to H.264/WebRTC instead of JPEG frames.
- Nice-to-haves: file transfer, clipboard sync, multi-monitor pick, per-agent
  "allow this session?" prompt on the host.
