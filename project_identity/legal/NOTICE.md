# 第三方代码声明

本项目（ROBOTarm_NEXUS）整体采用**专有授权（All Rights Reserved）**，版权所有 © 2026 Charles。
本项目运行时依赖以下第三方组件，这些组件保留其原始许可证，仅作为运行/编译依赖引入，不影响本项目的整体授权。

---

## 1. NVIDIA Isaac Sim

- **来源**: https://docs.isaacsim.omniverse.nvidia.com/
- **许可证**: NVIDIA Omniverse License Agreement（NVIDIA EULA）
- **用途**: 物理仿真渲染、PhysX、Kit 运行时、USD 资产管线
- **说明**: Isaac Sim 为 NVIDIA 提供的仿真平台，需单独安装并接受其 EULA。本项目不分发 Isaac Sim 本体。

---

## 2. NVIDIA Isaac Lab

- **来源**: https://github.com/isaac-sim/IsaacLab
- **许可证**: BSD-3-Clause License
- **版权**: Copyright (c) NVIDIA Corporation
- **用途**: DirectRLEnv 基类、环境配置框架、相机传感器、Articulation 配置接口
- **说明**: 本项目的 `core/env.py`、`core/env_cfg.py` 继承自 Isaac Lab 的 `DirectRLEnv`。

---

## 3. NVIDIA Lula

- **来源**: 随 Isaac Sim / Isaac Lab 分发
- **许可证**: NVIDIA EULA（随 Isaac Sim 分发）
- **用途**: position-only IK 后端、RMPFlow 运动规划、URDF / robot description 解析
- **说明**: 本项目的 `controllers/lula_ik.py` 通过 Lula 提供的 Curoco 后端求解 IK。

---

## 4. SO-101 机械臂设计

- **来源**: https://github.com/TheRobotStudio/SO-ARM100 （SO-101 Follower 变体）
- **许可证**: MIT License
- **版权**: Copyright (c) TheRobotStudio
- **用途**: 机械臂 USD 模型、关节命名语义、STS3215 伺服执行器参数
- **说明**: 本项目默认加载的 `so101_follower.usd` 及配套 Lula URDF / descriptor 派生自 SO-101 开源设计。本项目的抓取脚本与控制器代码为原创专有实现，不随 SO-101 的 MIT 授权发布。

---

## 5. Python 标准库与第三方包

以下 Python 包在运行时被引用，各自保留其原始许可证：

| 包名 | 许可证 | 用途 |
|------|--------|------|
| `numpy` | BSD-3-Clause | 数值计算 |
| `scipy` | BSD-3-Clause | `nexus_logo.py` 图像变换 |
| `Pillow` (PIL) | HPND/MIT | `nexus_logo.py` 图像加载 |

---

## 兼容性说明

本项目采用专有授权（All Rights Reserved）。第三方代码（NVIDIA EULA / BSD-3-Clause / MIT）作为依赖引入，其原始许可证仅覆盖第三方代码本身，不扩展到本项目的专有实现，也不影响本项目的整体授权。

任何对本项目的使用、运行、部署、复制、修改、传播或商业化行为，仍受根目录 [LICENSE.md](../../LICENSE.md) 的专有授权条款约束。
