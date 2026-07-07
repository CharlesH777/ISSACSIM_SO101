#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# run_ik.sh — Lula IK 冒烟测试（有 IK），双相机开启
#
# 作用：用原工程 Lula position-only IK 依次抓取并抬起 红/绿/蓝 三个方块。
#       读取 ~/.config/so101_control/ee_calibration.json 校准抓取点。
#
# 常用环境变量（均可覆盖）：
#   DEVICE       物理设备           默认 cuda:0
#   STEPS        额外控制预算       默认 150
#   HEADLESS     1=无头 / 0=GUI     默认 0（GUI 窗口，需要 DISPLAY）
#   DEBUG_IK     1=打印每步残差     默认 0
#
# 透传：脚本末尾的所有参数会原样追加到 isaaclab.sh 后面
#   例: ./scripts/run_ik.sh --steps 200
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
STEPS="${STEPS:-150}"
HEADLESS="${HEADLESS:-0}"
DEBUG_IK="${DEBUG_IK:-0}"

ARGS=()
[[ "$HEADLESS" == "1" ]] && ARGS+=(--headless)
ARGS+=(
  --device "$DEVICE"
  --enable_cameras
  --steps "$STEPS"
)

# 通过环境变量把 IK 调试开关传给 Python 进程
export SO101_DEBUG_IK="$DEBUG_IK"

echo "============================================================"
echo " ROBOTarm_NEXUS — Lula IK 冒烟测试（有 IK，双相机开启）"
echo "============================================================"
echo " device    : $DEVICE"
echo " steps     : $STEPS"
echo " headless  : $HEADLESS"
echo " debug_ik  : $DEBUG_IK"
echo " extra     : $*"
echo "------------------------------------------------------------"

exec "$ISAAC_LAUNCHER" -p -m ROBOTarm_NEXUS.scripts.run_ik "${ARGS[@]}" "$@"
