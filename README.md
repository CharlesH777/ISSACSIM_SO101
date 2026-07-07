# ROBOTarm_NEXUS

Standalone Isaac Lab package: **SO101 5-DOF arm + 3 cubes + dual cameras + Lula IK**.

A minimal, zero-dependency simulation environment extracted from the leisaac
codebase. Scene geometry, physics parameters, camera placement, lighting, and
IK controller are **fully aligned** with the `LeIsaac-SO101-GeneralizationTableSimple-v0`
data-collection task, so trajectories recorded here are directly compatible
with models trained on the collection pipeline.

```text
ROBOTarm_NEXUS/
├── pyproject.toml
├── README.md
├── .gitignore
├── docs/
│   └── HANDOVER.md
├── tools/
│   └── isaaclab.sh                # launcher wrapper (sources so101-clean env)
├── scripts/                       # user-facing run scripts
│   ├── run_env.sh                 # env smoke test (no IK)
│   ├── run_ik.sh                  # Lula IK cube-lift test
│   └── run_pick_place.sh          # Lula IK pick-and-place demo
└── ROBOTarm_NEXUS/                # Python package
    ├── __init__.py                # gym.register("SO101-MinimalCube-v0")
    ├── assets/
    │   ├── ik/lula/               # URDF + YAML (Lula kinematics)
    │   └── robots/                # optional bundled so101_follower.usd
    ├── core/
    │   ├── env.py                 # DirectRLEnv implementation
    │   ├── env_cfg.py             # DirectRLEnvCfg (physics/cameras/viewer)
    │   ├── scene_cfg.py           # table + 3 cubes + dual cameras + lights
    │   ├── robot_cfg.py           # ArticulationCfg + joint limits
    │   └── mdp.py                 # observations / reset / success
    ├── controllers/
    │   └── lula_ik.py             # dual-backend IK (manual DLS + Lula)
    └── scripts/
        ├── common.py              # shared helpers (camera strip / exit)
        ├── run_env.py             # env smoke test
        ├── run_ik.py              # IK cube-lift test
        └── demo_pick_place.py     # pick-and-place demo
```

## Quick Start

### 1. Prerequisites

- Isaac Sim 5.1 + Isaac Lab (tested on Ubuntu 22.04, RTX 3090)
- A sibling `so101-clean/` project with `scripts/env.sh` and `IsaacLab/`

### 2. Set the SO101 USD path

```bash
export SO101_USD_PATH=/path/to/so101_follower.usd
```

Or place a copy at `ROBOTarm_NEXUS/assets/robots/so101_follower.usd`.
If neither is set, the package auto-detects the USD from sibling projects.

### 3. Run

All scripts default to **GUI mode** with **both cameras enabled**.

```bash
cd ROBOTarm_NEXUS

# Environment smoke test (no IK, holds default pose)
./scripts/run_env.sh

# Lula IK — lift each cube in turn
./scripts/run_ik.sh

# Lula IK — pick one cube and place it at a target point
./scripts/run_pick_place.sh
```

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DEVICE` | `cuda:0` | Physics device |
| `NUM_ENVS` | `1` | Parallel environments (env test only) |
| `STEPS` | script-specific | Control steps per phase |
| `HEADLESS` | `0` | `1` = no GUI window |
| `CUBE` | `cube_red` | Target cube (pick-place demo) |
| `PLACE_X/Y/Z` | `0.18 / -0.58 / 0.44` | Placement target (pick-place demo) |
| `DEBUG_IK` | `0` | `1` = print IK residuals each step |
| `ZERO_ACTION` | `0` | `1` = zero joint targets (env test) |

## Physics Alignment

All scene geometry, physics parameters, camera intrinsics/extrinsics, lighting,
and actuator gains are aligned with `GeneralizationTableSimpleEnvCfg`:

| Parameter | Value |
|-----------|-------|
| `TABLE_CENTER` | `(-0.02, -0.42, 0.405)` |
| `ROBOT_BASE_POS` | `(TABLE_CENTER[0], +0.12, 0.395)` |
| `CUBE_SIZE` / positions | `0.03` / `(-0.10, 0.00, 0.10) × (-0.49, 0.44)` |
| `stiffness` / `damping` | `17.8 / 0.60` (STS3215 real servo) |
| `disable_gravity` | `True` (emulates firmware gravity compensation) |
| `enable_ccd` | `True` |
| `bounce_threshold_velocity` | `0.01` |
| `sun_light` | `950 intensity, 5000K` |
| `sky_light` | `45 intensity, 6000K` |
| front camera | `pos=(0,-0.45,0.6), focal=28.7, 640×480@30` |
| wrist camera | `pos=(-0.001,0.1,-0.04), focal=36.5, 640×480@30` |

## Public Imports

```python
import ROBOTarm_NEXUS
from ROBOTarm_NEXUS.controllers import (
    PlanarPanelIKConfig,
    PlanarSideViewJointController,
)
from isaaclab_tasks.utils import parse_env_cfg

env_cfg = parse_env_cfg("SO101-MinimalCube-v0", device="cuda:0", num_envs=1)
```

## Runtime Notes

- `tools/isaaclab.sh` sources `../so101-clean/scripts/env.sh`, prepends this repo
  root to `PYTHONPATH`, then delegates to Isaac Lab.
- `--enable_cameras --device cpu` is rejected before launch (tiled camera = CUDA-only).
- Smoke scripts default to `os._exit(0)` to avoid host-specific Kit shutdown hangs;
  set `SO101_FULL_SIM_SHUTDOWN=1` for normal cleanup debugging.
- `import ROBOTarm_NEXUS` only performs Gym registration — lightweight, no side effects.

Detailed implementation notes are in [docs/HANDOVER.md](docs/HANDOVER.md).
