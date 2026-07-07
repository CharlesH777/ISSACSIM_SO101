"""SO101 Minimal Sim — standalone SO101 + 3 cubes + dual cameras environment.

A self-contained Isaac Lab environment with:
  - SO101 5-DOF tabletop arm
  - Three colored 3cm cubes (red / green / blue)
  - Front + wrist cameras (640×480 @ 30 FPS)
  - Lula position-only IK controller
  - Joint-position action space (6D)

Zero dependency on the full leisaac codebase.
"""
import gymnasium as gym

gym.register(
    id="SO101-MinimalCube-v0",
    entry_point="ROBOTarm_NEXUS.core.env:SO101MinimalEnv",
    disable_env_checker=True,
    kwargs={
        "env_cfg_entry_point": "ROBOTarm_NEXUS.core.env_cfg:SO101MinimalEnvCfg",
    },
)
