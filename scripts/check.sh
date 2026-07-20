#!/usr/bin/env bash

set -euo pipefail

script_directory="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
project_directory="$(dirname -- "$script_directory")"
backend_directory="$project_directory/backend"
frontend_directory="$project_directory/frontend"
uv_cache_directory="${UV_CACHE_DIR:-/private/tmp/video-downloader-uv-cache}"

require_command() {
  local command_name="$1"
  local help_message="$2"

  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "Missing required command: $command_name" >&2
    echo "$help_message" >&2
    exit 1
  fi
}

require_command uv "Install uv before checking the backend."
require_command node "Install Node.js 24 LTS before checking the frontend."
require_command npm "Install npm together with Node.js 24 LTS."
require_command ffmpeg "Install FFmpeg 8 with Homebrew: brew install ffmpeg"
require_command ffprobe "ffprobe must be available alongside FFmpeg."

echo "Video Downloader MVP verification"
echo
echo "Toolchain:"
echo "  $(uv --version)"
echo "  Node.js $(node --version)"
echo "  npm $(npm --version)"
echo "  $(ffmpeg -version | head -n 1)"
echo

echo "Checking backend..."
(
  cd "$backend_directory"
  UV_CACHE_DIR="$uv_cache_directory" uv run --offline ruff format --check app migrations tests
  UV_CACHE_DIR="$uv_cache_directory" uv run --offline ruff check app migrations tests
  UV_CACHE_DIR="$uv_cache_directory" uv run --offline pytest
)

echo
echo "Checking frontend..."
(
  cd "$frontend_directory"
  npm run format
  npm run lint
  npm run build
  npm test
)

echo
echo "Automated MVP verification passed."
echo "Real YouTube, TikTok, playback, Finder, cancellation, and restart checks"
echo "remain manual; record them using docs/acceptance-results.md."
