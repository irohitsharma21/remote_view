#!/usr/bin/env bash
# Generate a self-signed TLS cert for LOCAL TESTING of wss://.
# For a real deployment use a proper cert (Let's Encrypt / Caddy / nginx).
set -e
cd "$(dirname "$0")/.."
mkdir -p certs
openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout certs/key.pem -out certs/cert.pem \
  -days 365 -subj "/CN=localhost"
echo "Wrote certs/key.pem and certs/cert.pem"
echo
echo "Run the server with TLS:"
echo "  uvicorn server.main:app --host 0.0.0.0 --port 8443 \\"
echo "      --ssl-keyfile certs/key.pem --ssl-certfile certs/cert.pem"
echo
echo "Then point the agent at it:  python agent/agent.py --server wss://YOURHOST:8443"
