#!/usr/bin/env bash
# play_logo_intro.sh — brief animated NEXUS logo intro (no log flooding).
#
# Plays N frames of the rotating ASCII logo, then returns. The screen is
# cleared only at the very start (nothing important is on it yet), the
# logo stays on top, and subsequent [INFO]/[ERR] logs print normally below.
#
# Safe under set -euo pipefail: all failures are caught with || true.
# Ctrl+C during the intro just skips it; the parent script keeps going.
#
# Usage:  play_logo_intro.sh [frames] [style]
#   frames  default 30  (~1.5 s at 20 fps)
#   style   default golden  (golden|blackgold|cyber|ice|matrix|ember|random)

set -euo pipefail

FRAMES="${1:-30}"
STYLE="${2:-golden}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOGO_SCRIPT="$ROOT_DIR/project_identity/logo/nexus_logo.py"

# Graceful fallback: skip silently if anything is missing.
[ -f "$LOGO_SCRIPT" ] || exit 0

# Skip if python3 or required deps are unavailable.
if ! /usr/bin/python3 -c 'import numpy, scipy.ndimage, PIL' 2>/dev/null; then
  exit 0
fi

# Play the intro. --bg none keeps background blank (no log flooding).
# --boot 0 skips TV-static noise. --no-hud hides frame counter.
# 2>/dev/null suppresses Python tracebacks; || true prevents set -e kill.
/usr/bin/python3 "$LOGO_SCRIPT" \
  --frames "$FRAMES" \
  --style "$STYLE" \
  --bg none \
  --boot 0 \
  --no-hud \
  --fps 20 \
  2>/dev/null || true
