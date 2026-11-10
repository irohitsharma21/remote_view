#!/usr/bin/env bash
# Start the relay server on the Mac with your chosen credentials.
# Override by exporting REMOTE_ADMIN_PASSWORD / REMOTE_AGENT_SECRET first.
set -e
cd "$(dirname "$0")/.."
source .venv/bin/activate

export REMOTE_ADMIN_PASSWORD="${REMOTE_ADMIN_PASSWORD:-mypass123}"
export REMOTE_AGENT_SECRET="${REMOTE_AGENT_SECRET:-mysecret}"

echo "=================================================="
echo " admin password : $REMOTE_ADMIN_PASSWORD"
echo " agent secret   : $REMOTE_AGENT_SECRET"
echo " dashboard      : http://localhost:8000"
echo "=================================================="
echo "In a SECOND terminal, expose it to the internet:"
echo "    cloudflared tunnel --url http://localhost:8000"
echo "then give the printed https URL (as wss://...) to the Windows agent."
echo "=================================================="

exec uvicorn server.main:app --host 0.0.0.0 --port 8000
