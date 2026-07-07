#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_SH="${SO101_ENV_SH:-$REPO_ROOT/../so101-clean/scripts/env.sh}"
ISAACLAB_SH="${ISAACLAB_SH:-/home/charles/ISAAC_SIM/IsaacLab/isaaclab.sh}"

if [[ ! -f "$ENV_SH" ]]; then
  echo "[ERROR] env.sh not found: $ENV_SH" >&2
  exit 1
fi

if [[ ! -x "$ISAACLAB_SH" ]]; then
  echo "[ERROR] Isaac Lab launcher not found or not executable: $ISAACLAB_SH" >&2
  exit 1
fi

# shellcheck disable=SC1090
source "$ENV_SH"

case ":${PYTHONPATH:-}:" in
  *":$REPO_ROOT:"*) ;;
  *) export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}" ;;
esac

exec "$ISAACLAB_SH" "$@"
