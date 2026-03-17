#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
NODE_PROJECT_DIR="$ROOT_DIR/vendor/js-reverse-mcp"

python3 -m venv "$ROOT_DIR/.venv"
"$ROOT_DIR/.venv/bin/python" -m pip install --upgrade pip
"$ROOT_DIR/.venv/bin/python" -m pip install -e "$ROOT_DIR"

if ! command -v node >/dev/null 2>&1; then
  echo "Error: node is required but was not found in PATH." >&2
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "Error: npm is required but was not found in PATH." >&2
  exit 1
fi

if [ ! -d "$NODE_PROJECT_DIR/node_modules/core-js" ]; then
  (
    cd "$NODE_PROJECT_DIR"
    npm install --ignore-scripts --no-package-lock
  )
fi

echo "Install complete."
echo "Command: $ROOT_DIR/.venv/bin/drissionpage-devtools-mcp"
