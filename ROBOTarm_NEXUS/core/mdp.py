"""MDP functions: observations, reset randomization, success check.

All functions follow the Isaac Lab ``func(env, env_ids, ...)`` convention
and have **no** dependency on leisaac.
"""
from __future__ import annotations

import math

import isaaclab.utils.math as math_utils
import torch
from isaaclab.assets import Articulation, RigidObject
from isaaclab.envs import DirectRLEnv
from isaaclab.managers import SceneEntityCfg
from isaaclab.sensors import FrameTransformer

from .scene_cfg import CUBE_DEFAULT_POSITIONS
from .specs import CUBE_NAMES


# ---------------------------------------------------------------------------
#  Observations
# ---------------------------------------------------------------------------
def joint_pos(env: DirectRLEnv, asset_cfg: SceneEntityCfg = SceneEntityCfg("robot")) -> torch.Tensor:
    asset: Articulation = env.scene[asset_cfg.name]
    return asset.data.joint_pos[:, asset_cfg.joint_ids]


def joint_vel(env: DirectRLEnv, asset_cfg: SceneEntityCfg = SceneEntityCfg("robot")) -> torch.Tensor:
    asset: Articulation = env.scene[asset_cfg.name]
    return asset.data.joint_vel[:, asset_cfg.joint_ids]


def ee_frame_state(
    env: DirectRLEnv,
    ee_frame_cfg: SceneEntityCfg = SceneEntityCfg("ee_frame"),
    robot_cfg: SceneEntityCfg = SceneEntityCfg("robot"),
) -> torch.Tensor:
    """End-effector pose (position + quaternion) in the robot base frame."""
    robot: Articulation = env.scene[robot_cfg.name]
    ee_frame: FrameTransformer = env.scene[ee_frame_cfg.name]
    ee_pos_w = ee_frame.data.target_pos_w[:, 0, :]
    ee_quat_w = ee_frame.data.target_quat_w[:, 0, :]
    pos_b, quat_b = math_utils.subtract_frame_transforms(
        robot.data.root_pos_w, robot.data.root_quat_w, ee_pos_w, ee_quat_w
    )
    return torch.cat([pos_b, quat_b], dim=1)


def joint_pos_target(env: DirectRLEnv, asset_cfg: SceneEntityCfg = SceneEntityCfg("robot")) -> torch.Tensor:
    asset: Articulation = env.scene[asset_cfg.name]
    return asset.data.joint_pos_target[:, asset_cfg.joint_ids]


# ---------------------------------------------------------------------------
#  Reset randomization — simple cube slot permutation
# ---------------------------------------------------------------------------
def randomize_cubes_permutation(
    env: DirectRLEnv,
    env_ids: torch.Tensor,
    cube_names: list[str] = CUBE_NAMES,
    slot_positions: tuple[tuple[float, float, float], ...] = CUBE_DEFAULT_POSITIONS,
    yaw_range: tuple[float, float] = (-30.0 * math.pi / 180, 30.0 * math.pi / 180),
):
    """Randomly permute cubes across fixed slots + add small yaw jitter.

    This keeps the scene simple while changing which color is where on each
    reset.  No rejection sampling needed — slots are pre-authored.
    """
    if len(env_ids) == 0:
        return
    device = env.device
    assets: list[RigidObject] = [env.scene[name] for name in cube_names]
    slots = torch.tensor(slot_positions, device=device, dtype=torch.float32)

    for env_id in env_ids.tolist():
        env_id_t = torch.tensor([env_id], device=device, dtype=torch.long)
        env_origin = env.scene.env_origins[env_id]
        perm = torch.randperm(len(cube_names), device=device)

        for i, asset in enumerate(assets):
            slot = slots[perm[i]]
            root_state = asset.data.default_root_state[env_id_t].clone()
            root_state[:, 0:3] += env_origin
            root_state[:, 0] = slot[0] + env_origin[0]
            root_state[:, 1] = slot[1] + env_origin[1]
            root_state[:, 2] = slot[2] + env_origin[2]
            yaw = torch.empty(1, device=device).uniform_(*yaw_range).item()
            half = yaw * 0.5
            root_state[:, 3] = math.cos(half)
            root_state[:, 4] = 0.0
            root_state[:, 5] = 0.0
            root_state[:, 6] = math.sin(half)
            root_state[:, 7:13] = 0.0
            asset.write_root_pose_to_sim(root_state[:, 0:7], env_ids=env_id_t)
            asset.write_root_velocity_to_sim(root_state[:, 7:13], env_ids=env_id_t)


# ---------------------------------------------------------------------------
#  Success criterion — any cube lifted above the table
# ---------------------------------------------------------------------------
def any_cube_lifted(
    env: DirectRLEnv,
    cube_names: list[str] = CUBE_NAMES,
    height_threshold: float = 0.08,
) -> torch.Tensor:
    """True when any cube is lifted ``height_threshold`` above the table surface."""
    table_z = env.scene["table_top"].data.root_pos_w[:, 2]
    success = torch.zeros(env.num_envs, dtype=torch.bool, device=env.device)
    for name in cube_names:
        cube_z = env.scene[name].data.root_pos_w[:, 2]
        success |= (cube_z - table_z) > height_threshold
    return success


def cube_positions(env: DirectRLEnv, cube_names: list[str] = CUBE_NAMES) -> torch.Tensor:
    """Return (N, num_cubes, 3) world positions of all cubes."""
    positions = [env.scene[name].data.root_pos_w for name in cube_names]
    return torch.stack(positions, dim=1)
