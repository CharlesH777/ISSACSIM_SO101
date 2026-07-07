"""Environment configuration for the minimal SO101 + 3 cubes task.

Uses ``DirectRLEnv`` (simpler than ManagerBasedRLEnv) with a 6-DOF
joint-position action space.
"""
from __future__ import annotations

import torch
from isaaclab.utils import configclass
from isaaclab.envs.direct_rl_env_cfg import DirectRLEnvCfg

from .scene_cfg import SO101MinimalSceneCfg, ROBOT_BASE_POS, ROBOT_BASE_ROT
from .specs import CUBE_NAMES


@configclass
class SO101MinimalEnvCfg(DirectRLEnvCfg):
    """Configuration for the SO101 minimal cube environment."""

    # --- scene ----------------------------------------------------------
    scene: SO101MinimalSceneCfg = SO101MinimalSceneCfg(
        env_spacing=8.0, num_envs=1
    )

    # --- spaces ---------------------------------------------------------
    action_space = 6
    state_space = {
        "joint_pos": 6,
        "joint_vel": 6,
        "ee_frame_state": 7,
        "joint_pos_target": 6,
    }
    observation_space = {
        "joint_pos": 6,
        "joint_pos_target": 6,
    }

    action_scale = 1.0

    # --- episode --------------------------------------------------------
    episode_length_s = 25.0
    decimation = 1

    # --- custom fields (not part of Isaac Lab base) ---------------------
    cube_names: list[str] = list(CUBE_NAMES)
    lift_height_threshold: float = 0.08

    def __post_init__(self) -> None:
        super().__post_init__()

        # --- physics (must be set in __post_init__, not class body) ------
        self.sim.physx.bounce_threshold_velocity = 0.01
        self.sim.physx.friction_correlation_distance = 0.00625
        # Match leisaac GeneralizationTableEnvCfg: CCD enabled.  GPU PhysX
        # may log a warning but the采集工程 keeps it on, so we align here.
        self.sim.physx.enable_ccd = True
        self.sim.render.enable_translucency = True
        # DLSS warns on the small 640x480 tiled cameras. FXAA is more stable for
        # this minimal environment and avoids the resize warning.
        self.sim.render.antialiasing_mode = "FXAA"

        # --- viewer -------------------------------------------------------
        self.viewer.eye = (-1.35, -1.55, 1.30)
        self.viewer.lookat = (-0.08, -0.36, 0.44)

        # Place the robot at the table edge
        self.scene.robot.init_state.pos = ROBOT_BASE_POS
        self.scene.robot.init_state.rot = ROBOT_BASE_ROT

        # Register camera observation spaces
        self.cameras = []
        for cam_name in ("front", "wrist"):
            cam_cfg = getattr(self.scene, cam_name, None)
            if cam_cfg is not None:
                self.state_space[cam_name] = [
                    cam_cfg.height, cam_cfg.width, 3
                ]
                self.observation_space[cam_name] = [
                    cam_cfg.height, cam_cfg.width, 3
                ]
                self.cameras.append(cam_name)

        # EE frame visualizer scale
        self.scene.ee_frame.visualizer_cfg.markers["frame"].scale = (
            0.05, 0.05, 0.05
        )
