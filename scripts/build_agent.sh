#!/usr/bin/env bash
# Package the agent into a single executable for the CURRENT OS.
#   - on macOS  -> a mac binary (dist/remote_agent)
#   - on Linux  -> a Linux binary
#   - a Windows .exe must be built ON WINDOWS (see build_agent.bat)
#
# Before building, edit the bake-in defaults at the top of agent/agent.py:
#   SERVER_DEFAULT = "wss://your-relay.example.com"
#   SECRET_DEFAULT = "your-shared-secret"
# so the distributed agent calls home without needing CLI args.
set -e
cd "$(dirname "$0")/.."
pip install pyinstaller >/dev/null
pyinstaller --onefile --noconsole --name remote_agent \
  --collect-submodules pynput \
  agent/agent.py
echo
echo "Built: dist/remote_agent"
