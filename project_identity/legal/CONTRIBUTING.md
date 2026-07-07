# 贡献指南

感谢你对 ROBOTarm_NEXUS 项目的兴趣！请阅读以下指南后再提交贡献。

## 1. 许可证

本项目采用 **专有授权（All Rights Reserved）**。版权所有 © 2026 Charles。
完整声明见根目录 [LICENSE.md](../../LICENSE.md)。

提交的代码将被视为作者的专有成果，其知识产权归作者所有。提交 PR 即表示你同意将贡献的知识产权转让给作者。

第三方代码必须保持其原始许可证不变，并在 `project_identity/legal/NOTICE.md` 中声明来源。

## 2. 开发环境

- **OS**: Ubuntu 22.04
- **Isaac Sim**: 5.1
- **Isaac Lab**: 随 Isaac Sim 5.1 配套
- **Python**: 3.10
- **GPU**: NVIDIA CUDA GPU（tiled camera 需要 CUDA）
- **构建系统**: Isaac Lab 的 `isaaclab.sh`

```bash
# 克隆并进入仓库
git clone <repo-url>
cd ROBOTarm_NEXUS

# 设置机械臂 USD 路径（必需）
export SO101_USD_PATH=/abs/path/to/so101_follower.usd

# 纯环境冒烟（先验证能否启动）
./scripts/run_env.sh
```

## 3. 代码规范

### Bash 脚本

- 使用 `#!/usr/bin/env bash`，不用 `#!/bin/bash`
- 开头加 `set -euo pipefail`（监控类脚本除外，可按需放宽）
- 路径用 `$ROOT_DIR` 动态解析，**禁止硬编码 `/home/用户名/...`**
- 用 `$ROOT_DIR` 模式：`ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"`
- 外部工作区路径必须支持环境变量覆盖：`${VAR:-$ROOT_DIR/...}`

### Python

- 遵循 PEP 8
- 路径用 `os.path` 或 `pathlib` 动态解析，**禁止硬编码绝对路径**
- 机器人命名真源统一从 `ROBOTarm_NEXUS/core/specs.py` 取值，不要在多个脚本里重复硬编码关节名、frame 名、USD 文件名
- 入口脚本（`run_env.py` / `run_ik.py` / `demo_pick_place.py`）共享逻辑统一走 `scripts/grasping_common.py`，不要在三个入口里复制同一套抓取逻辑

### 资产与配置

- 机械臂 USD、Lula URDF、robot description YAML 放在 `ROBOTarm_NEXUS/assets/` 下对应子目录
- 换机械臂时优先改 `core/specs.py`，再改 `core/robot_cfg.py`，最后才动 `controllers/lula_ik.py`
- 新增的相机 / 目标区 / 桌面几何改动集中在 `core/scene_cfg.py`

## 4. 提交规范

### Commit Message

```
<类型>: <简述>

<详细说明>
```

类型：
- `feat`: 新功能
- `fix`: 修复 bug
- `refactor`: 重构
- `docs`: 文档
- `build`: 构建系统
- `ci`: CI 配置
- `chore`: 杂项

### PR 流程

1. 从 `main` 拉分支：`git checkout -b feat/your-feature`
2. 确保 `./scripts/run_env.sh` 能正常启动
3. 确保仿真能跑：`./scripts/run_ik.sh` 或 `./scripts/run_pick_place.sh`
4. 提交 PR，描述改动内容和测试方法

### PR 检查清单

- [ ] 代码不包含硬编码的绝对路径
- [ ] 新增的机器人命名已收口到 `core/specs.py`
- [ ] 抓取逻辑改动落在 `scripts/grasping_common.py`，而非三个入口脚本各改一份
- [ ] `./scripts/run_env.sh` 能正常启动
- [ ] 改完机械臂后 `./scripts/run_ik.sh` 仍能完成 approach → descend → grasp → lift
- [ ] 没有提交 `__pycache__/`、`*.egg-info/`、`datasets/`、`IsaacLab/` 目录
- [ ] 没有 `print` / `console.log` 调试残留

## 5. 第三方代码

引入第三方代码时：
1. 在 `ROBOTarm_NEXUS/assets/` 或合适子目录下放置
2. 保留原始 LICENSE 文件
3. 在 `project_identity/legal/NOTICE.md` 中声明来源和许可证
4. 确认许可证与专有授权兼容（MIT、BSD-3-Clause、Apache-2.0 可作为第三方依赖引入，但不影响本项目整体授权）
