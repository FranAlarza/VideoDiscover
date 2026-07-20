#!/usr/bin/env bash

set -euo pipefail

script_directory="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
backend_directory="$(dirname -- "$script_directory")/backend"

cd "$backend_directory"
exec uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
