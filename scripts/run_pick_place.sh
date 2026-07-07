#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# run_pick_place.sh — Lula IK 抓放演示（有 IK），双相机开启
#
# 作用：启用 front+wrist 双相机，用原工程 Lula IK 抓取指定方块并放到目标点。
#       完整阶段：approach → descend → grasp → lift → transport →
#                 place → release → retreat
#
# 常用环境变量（均可覆盖）：
#   DEVICE       物理设备           默认 cuda:0
#   STEPS        额外控制预算       默认 90
#   HEADLESS     1=无头 / 0=GUI     默认 0（GUI 窗口，需要 DISPLAY）
#   CUBE         目标方块           默认 cube_red
#                                  (cube_red / cube_green / cube_blue)
#   PLACE_X      放置点 X (m)       默认 0.26
#   PLACE_Y      放置点 Y (m)       默认 -0.34
#   PLACE_Z      放置点 Z (m)       默认 0.4415
#
# 透传：脚本末尾的所有参数会原样追加到 isaaclab.sh 后面
#   例: ./scripts/run_pick_place.sh --cube cube_blue
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ISAAC_LAUNCHER="$REPO_ROOT/tools/isaaclab.sh"

if [[ ! -x "$ISAAC_LAUNCHER" ]]; then
  echo "[ERROR] 启动器不存在: $ISAAC_LAUNCHER" >&2
  exit 1
fi

DEVICE="${DEVICE:-cuda:0}"
STEPS="${STEPS:-90}"
HEADLESS="${HEADLESS:-0}"
CUBE="${CUBE:-cube_red}"
PLACE_X="${PLACE_X:-0.26}"
PLACE_Y="${PLACE_Y:--0.34}"
PLACE_Z="${PLACE_Z:-0.4415}"

ARGS=()
[[ "$HEADLESS" == "1" ]] && ARGS+=(--headless)
ARGS+=(
  --device "$DEVICE"
  --cube "$CUBE"
  --place "$PLACE_X" "$PLACE_Y" "$PLACE_Z"
  --steps "$STEPS"
)
# demo_pick_place.py 默认就开相机（除非 --no_cameras），这里不传 --no_cameras

echo "============================================================"
echo " ROBOTarm_NEXUS — Lula IK 抓放演示（有 IK，双相机开启）"
echo "============================================================"
echo " device    : $DEVICE"
echo " cube      : $CUBE"
echo " place     : ($PLACE_X, $PLACE_Y, $PLACE_Z)"
echo " steps     : $STEPS"
echo " headless  : $HEADLESS"
echo " extra     : $*"
echo "------------------------------------------------------------"

exec "$ISAAC_LAUNCHER" -p -m ROBOTarm_NEXUS.scripts.demo_pick_place "${ARGS[@]}" "$@"
