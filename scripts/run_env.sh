#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# run_env.sh — 纯环境冒烟测试（无 IK），双相机开启
#
# 作用：启动 SO101-MinimalCube-v0 环境，按默认姿态步进 N 帧，
#       打印观测/动作空间、方块位置、成功判定。不使用任何 IK 控制器。
#
# 常用环境变量（均可覆盖）：
#   DEVICE       物理设备           默认 cuda:0
#   NUM_ENVS     并行环境数         默认 1
#   STEPS        步进帧数           默认 200
#   HEADLESS     1=无头 / 0=GUI     默认 0（GUI 窗口，需要 DISPLAY）
#   ZERO_ACTION  1=全零关节目标     默认 0（保持默认姿态）
#
# 透传：脚本末尾的所有参数会原样追加到 isaaclab.sh 后面
#   例: ./scripts/run_env.sh --steps 60
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
NUM_ENVS="${NUM_ENVS:-1}"
STEPS="${STEPS:-200}"
HEADLESS="${HEADLESS:-0}"
ZERO_ACTION="${ZERO_ACTION:-0}"

ARGS=()
[[ "$HEADLESS" == "1" ]] && ARGS+=(--headless)
ARGS+=(
  --device "$DEVICE"
  --enable_cameras
  --num_envs "$NUM_ENVS"
  --steps "$STEPS"
)
[[ "$ZERO_ACTION" == "1" ]] && ARGS+=(--zero_action)

echo "============================================================"
echo " ROBOTarm_NEXUS — 环境冒烟测试（无 IK，双相机开启）"
echo "============================================================"
echo " device    : $DEVICE"
echo " num_envs  : $NUM_ENVS"
echo " steps     : $STEPS"
echo " headless  : $HEADLESS"
echo " zero_act  : $ZERO_ACTION"
echo " extra     : $*"
echo "------------------------------------------------------------"

exec "$ISAAC_LAUNCHER" -p -m ROBOTarm_NEXUS.scripts.run_env "${ARGS[@]}" "$@"
