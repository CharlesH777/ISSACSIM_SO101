#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TARGET_SCRIPT="$REPO_ROOT/scripts/isaaclab.sh"

if [[ ! -x "$TARGET_SCRIPT" ]]; then
  echo "[ERROR] local Isaac Lab launcher not found or not executable: $TARGET_SCRIPT" >&2
  exit 1
fi

exec "$TARGET_SCRIPT" "$@"
