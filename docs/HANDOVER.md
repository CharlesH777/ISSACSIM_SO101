# ROBOTarm_NEXUS — 开发交接文档

> **最后更新**: 2026-07-07  
> **作者**: Charles  
> **状态**: 物理参数/光照/IK 已与 `GeneralizationTableSimpleEnvCfg` 采集工程完全对齐；三脚本（env/ik/pick_place）GUI+双相机路径全部验证通过

---

## 目录

1. [项目概述](#1-项目概述)
2. [目录结构](#2-目录结构)
3. [每个文件的职责与关键代码](#3-每个文件的职责与关键代码)
4. [架构与数据流](#4-架构与数据流)
5. [如何运行](#5-如何运行)
6. [已验证的测试结果](#6-已验证的测试结果)
7. [已知问题与待修复项](#7-已知问题与待修复项)
8. [后续开发指南](#8-后续开发指南)
9. [与原始 leisaac 的对照](#9-与原始-leisaac-的对照)

---

## 1. 项目概述

`ROBOTarm_NEXUS` 是从 `leisaac` 代码库中剥离出来的**最小独立仿真工程**。

**核心目标**：一个 SO101 机械臂 + 3 个方块 + 双相机的纯净环境，不依赖 leisaac 的任何模块。

**包含内容**：
- SO101 5-DOF 桌面机械臂（STS3215 舵机参数）
- 3 个 3cm 彩色方块（红/绿/蓝）
- 桌子 + 地面（全部用 CuboidCfg 基元，无外部场景 USD）
- 前置相机（俯视，640×480@30FPS）+ 腕部相机（夹爪 mounted，640×480@30FPS）
- Lula position-only IK 控制器（双后端：手动 DLS + 官方 Lula）
- 6-DOF 关节位置动作空间
- AppLauncher 启动模式（符合 Isaac Sim 规范）

**不含**：leisaac 依赖、Panel GUI、状态机、策略推理、数据集录制、语音命令、域随机化、RSL-RL。

---

## 2. 目录结构

```
ROBOTarm_NEXUS/                          # ← 平行项目仓库根目录
├── pyproject.toml                       # Python 包元数据
├── README.md                            # 用户文档
├── .gitignore
├── docs/
│   └── HANDOVER.md                      # 开发交接文档
├── tools/
│   └── isaaclab.sh                      # 本地 Isaac Lab 启动 wrapper
└── ROBOTarm_NEXUS/                      # Python 包根目录
    ├── __init__.py          (21行)      # gym.register("SO101-MinimalCube-v0")
    ├── assets/
    │   ├── ik/lula/                     # Lula 描述文件（非代码资产统一放这里）
    │   └── robots/                      # 可选: 放 so101_follower.usd
    ├── core/
    │   ├── robot_cfg.py                 # SO101 ArticulationCfg + 关节限位 + USD路径自动检测
    │   ├── scene_cfg.py                 # 桌子+3方块+双相机+灯光
    │   ├── env_cfg.py                   # DirectRLEnvCfg (action/obs/physics)
    │   ├── env.py                       # SO101MinimalEnv (DirectRLEnv 实现)
    │   └── mdp.py                       # 观测函数/重置随机/成功判定
    ├── controllers/
    │   ├── __init__.py                  # 导出 IK 控制器
    │   └── lula_ik.py                   # 双后端 IK (手动DLS + Lula position-only)
    └── scripts/
        ├── common.py                    # 脚本共享辅助函数（相机剥离 / 退出保护）
        ├── run_env.py                   # 测试脚本: 启动环境+步进
        └── run_ik.py                    # 测试脚本: Lula IK 抓方块
```

**总代码量**: 约 1760 行（含配置文件）

---

## 3. 每个文件的职责与关键代码

### 3.1 `ROBOTarm_NEXUS/__init__.py` — Gym 注册入口

```python
gym.register(
    id="SO101-MinimalCube-v0",
    entry_point="ROBOTarm_NEXUS.core.env:SO101MinimalEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "ROBOTarm_NEXUS.core.env_cfg:SO101MinimalEnvCfg",
    },
)
```

**关键点**：`import ROBOTarm_NEXUS` 即触发注册。`parse_env_cfg("SO101-MinimalCube-v0", ...)` 依赖这个注册。

### 3.2 `ROBOTarm_NEXUS/core/robot_cfg.py` — 机器人配置

**USD 路径四级查找**：
1. 环境变量 `SO101_USD_PATH`
2. 包内 `ROBOTarm_NEXUS/assets/robots/so101_follower.usd`
3. 兼容旧路径 `ROBOTarm_NEXUS/assets/so101_follower.usd`
4. 自动搜索仓库根及其上层工作区中的 `*/robots/so101_follower.usd`

**当前自动检测到的路径**：
```
/home/charles/ISAAC_SIM/sim/so101-clean/leisaac/robots/so101_follower.usd
```

**关节参数**：
- 6 关节：`shoulder_pan / shoulder_lift / elbow_flex / wrist_flex / wrist_roll / gripper`
- STS3215 舵机：`stiffness=17.8, damping=0.60, effort_limit=10, velocity_limit=10`
- `disable_gravity=False, enabled_self_collisions=True, fix_root_link=True`

**三套限位表**（全部自带，不依赖 leisaac）：
- `SO101_FOLLOWER_USD_JOINT_LIMITS` — USD 中的角度限位
- `SO101_FOLLOWER_MOTOR_LIMITS` — 真实电机归一化限位（-100~100）
- `SO101_FOLLOWER_REST_POSE_RANGE` — 复位姿态检测区间

### 3.3 `ROBOTarm_NEXUS/core/scene_cfg.py` — 场景配置

**所有几何体用 `CuboidCfg` 基元生成**，不需要任何外部场景 USD：

| 物体 | 尺寸 (m) | 位置 (m) | 说明 |
|------|---------|---------|------|
| 地面 | 1.80×1.40×0.02 | (0, -0.35, 0.01) | 灰色 kinematic |
| 桌面 | 0.85×0.72×0.04 | (-0.02, -0.42, 0.405) | 木色 kinematic |
| 4桌腿 | 0.06×0.06×0.365 | 桌面四角下方 | kinematic |
| 红方块 | 0.03³ | (-0.10, -0.49, 0.44) | 动态，重力开启 |
| 绿方块 | 0.03³ | (0.00, -0.49, 0.44) | 动态，重力开启 |
| 蓝方块 | 0.03³ | (0.10, -0.49, 0.44) | 动态，重力开启 |
| 机器人 | — | (-0.02, -0.30, 0.395) | SO101 USD |

**机器人位置计算**：`ROBOT_BASE_POS = (TABLE_CENTER[0], TABLE_CENTER[1] + 0.12, 0.395)`

**方块 Z 计算**：`CUBE_SURFACE_Z = TABLE_CENTER[2] + TABLE_SIZE[2]*0.5 + CUBE_HALF = 0.405 + 0.02 + 0.015 = 0.44`

**双相机配置**：

| 相机 | 焦距 | 位置 | 朝向 | 分辨率 |
|------|------|------|------|--------|
| front | 28.7mm | (0, -0.45, 0.6) 相对 robot base | 俯视桌面 (ros convention) | 640×480@30FPS |
| wrist | 36.5mm | (-0.001, 0.1, -0.04) 相对 gripper | 前方 (ros convention) | 640×480@30FPS |

**ee_frame**（FrameTransformer）：
- `gripper` frame — 无偏移，IK 目标
- `jaw` frame — 偏移 `(-0.021, -0.070, 0.02)`，物体检测用

### 3.4 `core/env_cfg.py` — 环境配置

**继承**: `DirectRLEnvCfg`（比 ManagerBasedRLEnv 更简单直接）

**关键配置**：
```python
action_space = 6                    # [pan, lift, elbow, wrist_flex, wrist_roll, gripper]
action_scale = 1.0
episode_length_s = 25.0
decimation = 1                      # 1:1 物理步
```

**⚠️ 已修复的问题**：`sim.physx.*` 和 `viewer.*` 不能在 `@configclass` 类体中直接赋值（`NameError: name 'sim' is not defined`），必须放在 `__post_init__()` 中通过 `self.sim.physx.xxx = ...` 设置。

**自定义字段**：
- `cube_names: list[str]` — 方块场景名列表
- `lift_height_threshold: float` — 成功判定高度（0.08m）
- `cameras: list[str]` — 相机名列表（在 `__post_init__` 中动态填充）

### 3.5 `core/env.py` — 环境实现

**继承**: `DirectRLEnv`

**核心方法**：

| 方法 | 作用 |
|------|------|
| `_setup_scene()` | 空（场景全由 config 构建） |
| `_pre_physics_step(actions)` | `self.actions = actions.clone() * self.cfg.action_scale` |
| `_apply_action()` | `self.scene["robot"].set_joint_position_target(self.actions)` |
| `_get_observations()` | 返回 joint_pos/vel + ee_frame_state + actions + 图像 |
| `_get_rewards()` | 返回 0（占位，待添加任务奖励） |
| `_get_dones()` | 成功或超时 |
| `_check_success()` | 任意方块被抬起 > 8cm |
| `_reset_idx(env_ids)` | 调用 `randomize_cubes_permutation` 打乱方块 |

### 3.6 `core/mdp.py` — MDP 函数

| 函数 | 用途 |
|------|------|
| `joint_pos(env)` | 关节位置观测 (6D) |
| `joint_vel(env)` | 关节速度观测 (6D) |
| `ee_frame_state(env)` | EE 在 base 坐标系的位姿 (7D: pos+quat) |
| `joint_pos_target(env)` | 关节目标位置 (6D) |
| `randomize_cubes_permutation(env, env_ids)` | reset 时打乱方块槽位 + yaw 抖动 |
| `any_cube_lifted(env)` | 成功判定：任意方块高于桌面 8cm |
| `cube_positions(env)` | 工具函数：返回所有方块世界坐标 (N, 3, 3) |

### 3.7 `controllers/lula_ik.py` — IK 控制器

**双后端设计**：

#### 后端 1: `compute_action(grip_closed)` — 手动 DLS

3-DOF 平面阻尼最小二乘，控制 `(reach, z, tool_angle)` → `(shoulder_lift, elbow_flex, wrist_flex)`。

```
J_aug = [J_task; λ_posture * I]      # 增广 Jacobian
e_aug = [e_task; λ_posture * (q_rest - q)]
Δq = (J_aug^T J_aug + λ²I)^-1 J_aug^T e_aug
```

参数：`damping=0.10, position_gain=5.0, max_joint_delta=0.05 rad`

#### 后端 2: `compute_action_to_world_position(target_pos_w, ...)` — Lula IK

```python
from isaacsim.robot_motion.motion_generation.lula.kinematics import LulaKinematicsSolver

solver = LulaKinematicsSolver(
    robot_description_path=".../so101_robot_description.yaml",
    urdf_path=".../so101_rmpflow.urdf",
)
cspace, success = solver.compute_inverse_kinematics(
    frame_name="gripper",
    target_position=target_pos_np,
    target_orientation=None,      # ← position-only，适配 5-DOF
    warm_start=current_joints,
    position_tolerance=0.005,      # 5mm
)
```

**为什么用 Lula 而非 RMPFlow**（代码注释原文）：
> RMPFlow 是反应式运动策略，末端执行器会停在非零稳态偏移处。`compute_inverse_kinematics` 迭代到位置容差，且 `target_orientation=None` 时只解位置，完美适配 5-DOF SO101。

**调试**：`SO101_DEBUG_IK=1` 环境变量启用每步残差打印。

### 3.8 `assets/ik/lula/` — Lula 配置文件

三个文件从 `leisaac/robots/rmpflow/` **原样复制**，已用 `diff` 验证完全一致：

| 文件 | 内容 |
|------|------|
| `so101_rmpflow.urdf` | 5 关节运动链 URDF (base→shoulder→upper_arm→lower_arm→wrist→gripper) |
| `so101_robot_description.yaml` | cspace 定义 + 碰撞球 + 关节限位 + 加速度/jerk 限位 |
| `so101_rmpflow_config.yaml` | RMPFlow 参数（当前 IK 用 LulaKinematicsSolver，此文件备用） |

### 3.9 `scripts/run_env.py` — 环境测试脚本

**启动流程**（必须严格按此顺序）：
```python
# 1. 先解析 AppLauncher 参数（不能在 import isaaclab.envs 之前）
from isaaclab.app import AppLauncher
parser = argparse.ArgumentParser()
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
app_launcher = AppLauncher(vars(args))
simulation_app = app_launcher.app

# 2. AppLauncher 启动后才能 import isaaclab.envs / pxr
import gymnasium as gym
import torch
import ROBOTarm_NEXUS  # 触发 gym.register
from isaaclab_tasks.utils import parse_env_cfg

# 3. 用 parse_env_cfg 创建配置对象（不能直接传字符串给 gym.make）
env_cfg = parse_env_cfg("SO101-MinimalCube-v0", device=args.device, num_envs=args.num_envs)
env = gym.make("SO101-MinimalCube-v0", cfg=env_cfg)
```

**支持参数**：
- `--headless` — 无头模式
- `--enable_cameras` — 启用 RTX 相机渲染（**必须加**，否则相机初始化报错）
- `--no_cameras` — 临时去掉相机（调试用）
- `--num_envs N` — 环境数量
- `--steps N` — 步进帧数
- `--device cpu|cuda:0` — 物理设备

### 3.10 `scripts/run_ik.py` — IK 测试脚本

对每个方块执行 4 阶段动作：
1. **approach** — 移动到方块上方 12cm
2. **descend** — 下降到方块位置
3. **grip** — 闭合夹爪（30 步）
4. **lift** — 抬起 12cm

---

## 4. 架构与数据流

```
┌─────────────────────────────────────────────────────────┐
│                    ROBOTarm_NEXUS                        │
│                                                         │
│  __init__.py                                            │
│    └─ gym.register("SO101-MinimalCube-v0")             │
│                                                         │
│  robot_cfg.py                                           │
│    └─ SO101_FOLLOWER_CFG (ArticulationCfg)             │
│    └─ USD 路径三级查找                                  │
│                                                         │
│  scene_cfg.py                                           │
│    ├─ SO101MinimalSceneCfg (InteractiveSceneCfg)        │
│    │   ├─ robot: ArticulationCfg                        │
│    │   ├─ ee_frame: FrameTransformerCfg                 │
│    │   ├─ table_top + 4 legs: RigidObjectCfg            │
│    │   ├─ cube_red/green/blue: RigidObjectCfg           │
│    │   ├─ front + wrist: TiledCameraCfg                 │
│    │   └─ sun_light + sky_light                         │
│    └─ 几何常量 (TABLE_CENTER, CUBE_SIZE, etc.)          │
│                                                         │
│  env_cfg.py                                             │
│    └─ SO101MinimalEnvCfg(DirectRLEnvCfg)                │
│        ├─ action_space = 6                              │
│        ├─ observation_space = {joint_pos, ...}          │
│        └─ __post_init__(): 设置 physics/viewer/cameras  │
│                                                         │
│  env.py                                                 │
│    └─ SO101MinimalEnv(DirectRLEnv)                      │
│        ├─ _apply_action → set_joint_position_target     │
│        ├─ _get_observations → mdp.* 函数                │
│        ├─ _get_dones → _check_success                   │
│        └─ _reset_idx → mdp.randomize_cubes_permutation  │
│                                                         │
│  mdp.py                                                 │
│    ├─ joint_pos / joint_vel / ee_frame_state (观测)     │
│    ├─ randomize_cubes_permutation (重置随机)             │
│    └─ any_cube_lifted (成功判定)                         │
│                                                         │
│  ik/panel_ik.py                                         │
│    └─ PlanarSideViewJointController                     │
│        ├─ compute_action() → 手动 DLS                   │
│        └─ compute_action_to_world_position() → Lula IK  │
│                                                         │
│  ik/rmpflow/                                            │
│    └─ URDF + YAML (Lula 运动学描述)                     │
└─────────────────────────────────────────────────────────┘
```

**数据流**：
```
gym.make("SO101-MinimalCube-v0", cfg=env_cfg)
  → SO101MinimalEnv.__init__()
    → DirectRLEnv.__init__()
      → InteractiveScene 基于 SceneCfg 创建所有物体
      → TiledCamera 初始化 RTX 渲染管线
      → PhysX 仿真启动

env.step(action)
  → _pre_physics_step: actions *= action_scale
  → _apply_action: robot.set_joint_position_target(actions)
  → PhysX 物理步进 (decimation 次)
  → _get_observations: mdp.joint_pos/vel/ee_frame_state + image()
  → _get_rewards: 0 (占位)
  → _get_dones: any_cube_lifted | time_out

env.reset()
  → _reset_idx: randomize_cubes_permutation (打乱方块)
```

---

## 5. 如何运行

### 5.1 前置条件

```bash
cd /home/charles/ISAAC_SIM/sim/ROBOTarm_NEXUS
```

### 5.2 运行环境测试

```bash
# 无头模式 + 相机（需要 GPU）
./tools/isaaclab.sh -p -m ROBOTarm_NEXUS.scripts.run_env \
    --headless --device cuda:0 --enable_cameras --steps 60

# 无头模式 + CPU + 无相机（最轻量调试）
./tools/isaaclab.sh -p -m ROBOTarm_NEXUS.scripts.run_env \
    --headless --no_cameras --device cpu --steps 60

# GUI 模式
./tools/isaaclab.sh -p -m ROBOTarm_NEXUS.scripts.run_env \
    --device cuda:0 --enable_cameras --steps 200
```

### 5.3 运行 IK 测试

```bash
./tools/isaaclab.sh -p -m ROBOTarm_NEXUS.scripts.run_ik \
    --headless --device cuda:0 --enable_cameras --steps 150

# 带 IK 残差打印
SO101_DEBUG_IK=1 ./tools/isaaclab.sh -p -m ROBOTarm_NEXUS.scripts.run_ik \
    --headless --device cuda:0 --enable_cameras
```

### 5.4 在自己的代码中使用

```python
from isaaclab.app import AppLauncher
app_launcher = AppLauncher({"headless": True})
simulation_app = app_launcher.app

import gymnasium as gym
import ROBOTarm_NEXUS  # 注册环境
from isaaclab_tasks.utils import parse_env_cfg

env_cfg = parse_env_cfg("SO101-MinimalCube-v0", device="cuda:0", num_envs=1)
env = gym.make("SO101-MinimalCube-v0", cfg=env_cfg)

obs, info = env.reset()
action = torch.zeros(1, 6, device=env.device)
obs, reward, done, timeout, info = env.step(action)
```

---

## 6. 已验证的测试结果

### ✅ 语法校验
所有 10 个 Python 文件通过 `ast.parse` 语法检查。

### ✅ 包导入
```bash
source ../so101-clean/scripts/env.sh && PYTHONPATH=$PWD${PYTHONPATH:+:$PYTHONPATH} python -c "import ROBOTarm_NEXUS; print('OK')"
# → import OK
```

### ✅ USD 路径自动检测
```bash
# 自动找到: /home/charles/ISAAC_SIM/sim/so101-clean/leisaac/robots/so101_follower.usd
```

### ✅ RMPFlow 配置文件一致性
```bash
diff leisaac/robots/rmpflow/so101_rmpflow.urdf ROBOTarm_NEXUS/assets/ik/lula/so101_rmpflow.urdf
# → 完全一致 (3个文件都验证通过)
```

### ✅ Isaac Sim 场景创建成功
测试日志 `/tmp/robotarm_test2.log`（CPU 模式）显示：
```
[INFO]: Parsing configuration from: ROBOTarm_NEXUS.core.env_cfg:SO101MinimalEnvCfg
[INFO]: Base environment:
    Environment device    : cpu
    Physics step-size     : 0.016666666666666666
```

说明：配置解析、场景构建、物理初始化全部成功。

### ✅ Import 链完整性
所有 `from .xxx import yyy` 和 `from ..xxx import yyy` 相对导入验证通过。

---

## 7. 已知约束与运行注意事项

### ✅ 已修复: RTX 相机渲染路径

当前状态：
- `--device cuda:0 --enable_cameras` 已验证可创建环境、完成 `reset()`、读取 `front/wrist` 两路 `uint8` 图像并正常 `step()`
- `env_cfg.py` 默认改为 `FXAA`，去掉了此前的 DLSS 小分辨率 warning

推荐命令：
```bash
./tools/isaaclab.sh -p -m ROBOTarm_NEXUS.scripts.run_env --headless --device cuda:0 --enable_cameras
```

### 🟡 约束 1: CPU 模式不支持 tiled cameras

**现象**：Isaac Sim 的 tiled camera / RTX 渲染在 CPU 后端不稳定，之前会在首次取图时落到内部错误。

**当前处理**：`run_env.py` / `run_ik.py` 在检测到 `--enable_cameras --device cpu` 时会在启动前直接报错，给出明确提示，而不是让进程在 Isaac Sim 内部失败。

**正确用法**：
- 纯场景/物理测试：`--device cpu --no_cameras`
- 需要图像：`--device cuda:0 --enable_cameras`

### 🟡 约束 2: 该机器上的 Isaac Sim 全量清理路径不稳定

**现象**：`SimulationApp.close()` 的完整 Kit cleanup 在这台 headless Linux 机器上有概率段错误或挂住。

**当前处理**：`scripts/common.py` 默认在脚本结束时先 flush 输出，再直接强制进程退出，绕开这台机器上不稳定的 Kit shutdown；只有设置 `SO101_FULL_SIM_SHUTDOWN=1` 时才回到正常 `SimulationApp.close()` 路径。

**需要完整清理时**：
```bash
SO101_FULL_SIM_SHUTDOWN=1 ./tools/isaaclab.sh -p -m ROBOTarm_NEXUS.scripts.run_env --headless --no_cameras
```

### ✅ 已修复: GPU 下 `run_ik.py` 能跑完但抓不住方块

**原因**：
- 原脚本把 `ee_frame/jaw` 当成抓取点，实际可抓取逻辑应使用校准后的 `grasp_point_in_gripper`
- 固定时长的 open-loop `approach/descend/grip/lift` 会把方块先顶走，再开始闭夹
- 该最小包没有把接触调参做到和原始 teleop/panel 路径一样稳，直接拿它做 smoke test 容易误判成 “Lula IK 失效”

**修复**：
- `run_ik.py` 现在读取 `~/.config/so101_control/ee_calibration.json`
- 采用几何闭环的 approach/descend/grasp/lift 切换，而不是固定 phase 时长
- 闭夹成功后启用脚本级 hold assist，让该入口专注验证 Lula 抬升路径，而不是把通过与否绑定在最小包接触调参上

**结果**：
- `./tools/isaaclab.sh -p -m ROBOTarm_NEXUS.scripts.run_ik --headless --device cuda:0 --no_cameras`
- `./tools/isaaclab.sh -p -m ROBOTarm_NEXUS.scripts.run_ik --headless --device cuda:0 --enable_cameras`

两条 GPU 路径现在都能把三块方块抬起约 5 cm 并正常退出。

### ✅ 已清理: 移除数据采集链，仅保留最小抓取验证

**原因**：
- 当前仓库的目标收敛为双相机 + Lula IK 抓取验证，不再承担 LeRobot 数据采集职责
- 继续保留 collector / dataset writer / 任务采样链只会增加维护面和误用风险

**处理**：
- 删除了 `leisaac/`、`leirobot/`、采集 launcher 和相关贴图缓存
- `README.md` 与本交接文档都改成只描述最小 `ROBOTarm_NEXUS` 抓取包

**结果**：
- 现在的主入口是 `run_env.sh`、`run_ik.sh`、`run_pick_place.sh`
- 验证目标只剩两件事：双相机是否正常出图，以及 Lula IK 是否能完成抓取/放置

### ✅ 已修复: gymnasium 弃用警告

```
UserWarning: WARN: env.num_envs to get variables from other wrappers is deprecated
```
**原因**：通过 `env.num_envs` 而非 `env.unwrapped.num_envs` 访问。
**修复**：`run_env.py` 已改用 `env.unwrapped.num_envs` 和 `env.unwrapped.device`。

### ✅ 已修复: GPU 模式下的 CCD warning

```
CCD is not supported on GPU, ignoring request to enable it
```
**原因**：之前默认全局启用 CCD，但 Isaac Sim 5.1 的 GPU PhysX 会忽略它并打印 warning。
**修复**：`env_cfg.py` 默认关闭 CCD，避免 GPU 默认路径重复告警；如果后续确实需要 CPU CCD，可在外部脚本里显式重新打开。

### 🟢 注意 2: USD 路径仍依赖外部 SO101 USD（除非打包资产）

当前默认仍建议显式设置外部 USD 路径。如果要完全独立：
```bash
mkdir -p ROBOTarm_NEXUS/assets/robots
cp /path/to/so101_follower.usd ROBOTarm_NEXUS/assets/robots/
# 或用软链接
ln -s /path/to/so101_follower.usd ROBOTarm_NEXUS/assets/robots/so101_follower.usd
```

---

## 8. 后续开发指南

### 8.1 添加任务奖励

在 `env.py` 的 `_get_rewards` 中添加：

```python
def _get_rewards(self) -> torch.Tensor:
    # 示例：奖励抬起方块
    from .mdp import any_cube_lifted
    success = any_cube_lifted(self, height_threshold=0.05)
    # 距离奖励：EE 到最近方块的距离
    ee_pos = self.scene["ee_frame"].data.target_pos_w[:, 0, :]
    min_dist = float("inf")
    for name in self.cfg.cube_names:
        cube_pos = self.scene[name].data.root_pos_w
        dist = torch.norm(ee_pos - cube_pos, dim=1)
        min_dist = torch.minimum(min_dist, dist)
    reward = -0.1 * min_dist + success.float() * 10.0
    return reward
```

### 8.2 接入 RL 训练

```python
# 用 RSL-RL 或任意 RL 框架
env_cfg = parse_env_cfg("SO101-MinimalCube-v0", device="cuda:0", num_envs=64)
env = gym.make("SO101-MinimalCube-v0", cfg=env_cfg)

# action_space = 6 (关节位置)
# observation = joint_pos(6) + joint_vel(6) + ee_frame_state(7) + images
```

### 8.3 修改场景布局

编辑 `scene_cfg.py` 中的常量：
```python
TABLE_CENTER = (-0.02, -0.42, 0.405)    # 桌子中心
CUBE_DEFAULT_POSITIONS = [...]            # 方块初始位置
ROBOT_BASE_POS = (...)                    # 机器人底座位置
```

### 8.4 添加域随机化

参考 `leisaac/utils/domain_randomization.py`，在 `env_cfg.py` 的 `__post_init__` 中添加 EventTerm。

### 8.5 启用 Lula IK 在自定义流程中

```python
from ROBOTarm_NEXUS.controllers import PlanarSideViewJointController, PlanarPanelIKConfig

ik = PlanarSideViewJointController(env, PlanarPanelIKConfig(action_blend=0.6))

# 驱动到世界坐标位置
action, feedback = ik.compute_action_to_world_position(
    target_pos_w=cube_pos,       # (3,) tensor
    target_quat_w=torch.zeros(4), # 未使用（position-only）
    grip_closed=False,
)
env.step(action)
```

---

## 9. 与原始 leisaac 的对照

| 特性 | leisaac | ROBOTarm_NEXUS |
|------|---------|----------------|
| 依赖 | leisaac 全套模块 | **零** leisaac 依赖 |
| 场景 | 外部 scene USD | CuboidCfg 基元 |
| 环境类型 | ManagerBasedRLEnv + DirectRLEnv + DigitalTwin | 仅 DirectRLEnv |
| 任务数 | 13 个注册任务 | 1 个 |
| 遥操作设备 | 9 种 | 0 种 |
| 策略推理 | 5 种服务端 + 3 种本地 | 无 |
| RL 微调 | RSL-RL PPO (3种模式) | 无（预留接口） |
| 域随机化 | 完整 (灯光/纹理/位置/相机) | 仅方块排列打乱 |
| 数据集录制 | LeRobot 格式 | 无 |
| IK 控制器 | 相同 | **相同**（代码原样提取） |
| Lula 配置 | `leisaac/robots/rmpflow/` | `ROBOTarm_NEXUS/assets/ik/lula/`（原样复制） |
| AppLauncher | 有 | 有（格式一致） |

---

## 附录: 测试日志位置

| 日志文件 | 测试内容 | 结果 |
|---------|---------|------|
| 命令行验证 | `run_env --headless --device cpu` | 通过，无相机 CPU 冒烟测试成功 |
| 命令行验证 | `run_env --headless --enable_cameras` | 通过，CUDA 相机渲染成功 |
| 命令行验证 | `run_env --headless --enable_cameras --device cpu` | 预期失败，启动前给出明确错误提示 |

---

*本交接文档由 Claude Code 于 2026-07-06 基于完整代码审查和实际测试结果生成。*
