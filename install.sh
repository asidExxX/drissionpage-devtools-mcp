#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

python3 -m venv "$ROOT_DIR/.venv"
"$ROOT_DIR/.venv/bin/python" -m pip install --upgrade pip
"$ROOT_DIR/.venv/bin/python" -m pip install -e "$ROOT_DIR"

echo "Install complete."
echo "Command: $ROOT_DIR/.venv/bin/drissionpage-devtools-mcp"
