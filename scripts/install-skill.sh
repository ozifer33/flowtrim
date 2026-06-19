#!/usr/bin/env sh
set -eu

if ! command -v node >/dev/null 2>&1; then
  echo "node is required for this convenience installer. Use docs/install.md for manual copy paths." >&2
  exit 1
fi

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
exec node "$SCRIPT_DIR/flowtrim-skill-install.mjs" "$@"
