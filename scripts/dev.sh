#!/usr/bin/env bash

set -euo pipefail

script_directory="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_directory="$(dirname -- "$script_directory")"
backend_directory="$project_directory/backend"
frontend_directory="$project_directory/frontend"
uv_cache_directory="${UV_CACHE_DIR:-/private/tmp/video-downloader-uv-cache}"
restart_requested=false

backend_pid=""
frontend_pid=""

if [[ "${1:-}" == "--restart" ]]; then
  restart_requested=true
elif [[ $# -gt 0 ]]; then
  echo "Usage: ./scripts/dev.sh [--restart]" >&2
  exit 2
fi

cleanup() {
  if [[ -n "$frontend_pid" ]] && kill -0 "$frontend_pid" 2>/dev/null; then
    kill "$frontend_pid"
  fi
  if [[ -n "$backend_pid" ]] && kill -0 "$backend_pid" 2>/dev/null; then
    kill "$backend_pid"
  fi
}

trap cleanup EXIT INT TERM

process_using_port() {
  local port="$1"
  lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null | head -n 1
}

print_port_owner() {
  local port="$1"
  lsof -nP -iTCP:"$port" -sTCP:LISTEN 2>/dev/null || true
}

stop_port_owner() {
  local port="$1"
  local pid
  pid="$(process_using_port "$port")"

  if [[ -n "$pid" ]]; then
    echo "Stopping process $pid using port $port"
    kill "$pid"
  fi
}

ensure_port_available() {
  local port="$1"
  local label="$2"

  if [[ -z "$(process_using_port "$port")" ]]; then
    return
  fi

  if [[ "$restart_requested" == true ]]; then
    stop_port_owner "$port"
    sleep 1
    if [[ -z "$(process_using_port "$port")" ]]; then
      return
    fi
  fi

  echo "$label cannot start because port $port is already in use." >&2
  print_port_owner "$port" >&2
  echo >&2
  echo "Close that process or run: ./scripts/dev.sh --restart" >&2
  exit 1
}

ensure_port_available 8000 "Backend"
ensure_port_available 5173 "Frontend"

echo "Starting backend on http://127.0.0.1:8000"
(
  cd "$backend_directory"
  UV_CACHE_DIR="$uv_cache_directory" uv run --offline uvicorn app.main:app \
    --host 127.0.0.1 \
    --port 8000
) &
backend_pid="$!"

echo "Starting frontend on http://127.0.0.1:5173"
(
  cd "$frontend_directory"
  npm run dev -- --host 127.0.0.1
) &
frontend_pid="$!"

echo
echo "Video Downloader is starting:"
echo "  Backend:  http://127.0.0.1:8000"
echo "  Frontend: http://127.0.0.1:5173"
echo
echo "Press Ctrl+C to stop both servers."

while kill -0 "$backend_pid" 2>/dev/null && kill -0 "$frontend_pid" 2>/dev/null; do
  sleep 1
done
