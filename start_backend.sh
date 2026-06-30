#!/usr/bin/env bash
# Start Qwen Council backend server
set -euo pipefail

cd "$(dirname "$0")"

# Kill any existing server on port 8000
fuser -k 8000/tcp 2>/dev/null || true
sleep 0.5

# Start uvicorn in background
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 \
    > /tmp/uvicorn_8000.log 2>&1 &

PID=$!
disown

# Wait for startup
for i in $(seq 1 10); do
    sleep 1
    if curl -sf http://localhost:8000/api/health >/dev/null 2>&1; then
        echo "Backend running (PID: $PID)"
        exit 0
    fi
done

echo "Backend failed to start (check /tmp/uvicorn_8000.log)"
exit 1
