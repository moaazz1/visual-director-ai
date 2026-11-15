#!/usr/bin/env bash
set -euo pipefail
cd /app
/opt/director/bin/uvicorn api.main:app --host 127.0.0.1 --port 8000 &
api_pid=$!
cd /app/web
node node_modules/next/dist/bin/next start --hostname 0.0.0.0 --port "${PORT:-3000}" &
web_pid=$!
trap 'kill "$api_pid" "$web_pid" 2>/dev/null || true' EXIT
wait -n "$api_pid" "$web_pid"
