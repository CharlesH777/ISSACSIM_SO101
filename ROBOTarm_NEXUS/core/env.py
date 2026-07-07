"""DirectRLEnv implementation: SO101 + 3 cubes + dual cameras.

Action space:  6-DOF joint position targets
                  [shoulder_pan, shoulder_lift, elbow_flex,
                   wrist_flex, wrist_roll, gripper]

Observations:  joint_pos (6) + joint_vel (6) + ee_frame_state (7) +
               joint_pos_target (6) + front_image (640×480×3) +
               wrist_image (640×480×3)

Reward:        0.0 (placeholder — add your own task reward)

Success:       any cube lifted > ``lift_height_threshold`` above the table
"""
from __future__ import annotations

import torch
from isaaclab.envs import DirectRLEnv
from isaaclab.envs.mdp import image
from isaaclab.managers import SceneEntityCfg

from .env_cfg import SO101MinimalEnvCfg
from . import mdp


class SO101MinimalEnv(DirectRLEnv):
    """Minimal SO101 cube-lifting environment."""

    cfg: SO101MinimalEnvCfg

    def __init__(self, cfg: SO101MinimalEnvCfg, render_mode: str | None = None, **kwargs):
        super().__init__(cfg, render_mode, **kwargs)
        self.actions = self.scene["robot"].data.default_joint_pos.clone()

    # ------------------------------------------------------------------
    #  Scene setup
    # ------------------------------------------------------------------
    def _setup_scene(self):
        """Scene is built from the config; no extra setup needed."""
        pass

    # ------------------------------------------------------------------
    #  Action processing
    # ------------------------------------------------------------------
    def _pre_physics_step(self, actions: torch.Tensor) -> None:
        self.actions = actions.clone() * self.cfg.action_scale

    def _apply_action(self) -> None:
        self.scene["robot"].set_joint_position_target(self.actions)

    # ------------------------------------------------------------------
    #  Observations
    # ------------------------------------------------------------------
    def _get_observations(self) -> dict:
        obs = {
            "policy": {
                "joint_pos": mdp.joint_pos(self),
                "joint_vel": mdp.joint_vel(self),
                "ee_frame_state": mdp.ee_frame_state(self),
                "joint_pos_target": mdp.joint_pos_target(self),
                "actions": self.actions,
            }
        }
        for cam in self.cfg.cameras:
            obs["policy"][cam] = image(
                self,
                sensor_cfg=SceneEntityCfg(cam),
                data_type="rgb",
                normalize=False,
            )
        return obs

    # ------------------------------------------------------------------
    #  Rewards
    # ------------------------------------------------------------------
    def _get_rewards(self) -> torch.Tensor:
        return torch.zeros(self.num_envs, device=self.device)

    # ------------------------------------------------------------------
    #  Termination
    # ------------------------------------------------------------------
    def _get_dones(self) -> tuple[torch.Tensor, torch.Tensor]:
        time_out = self.episode_length_buf >= self.max_episode_length - 1
        success = self._check_success()
        # End episode on success or timeout
        done = success | time_out
        return done, time_out

    def _check_success(self) -> torch.Tensor:
        return mdp.any_cube_lifted(
            self,
            cube_names=self.cfg.cube_names,
            height_threshold=self.cfg.lift_height_threshold,
        )

    # ------------------------------------------------------------------
    #  Reset customization
    # ------------------------------------------------------------------
    def _reset_idx(self, env_ids: torch.Tensor):
        super()._reset_idx(env_ids)
        robot = self.scene["robot"]
        joint_pos = robot.data.default_joint_pos[env_ids].clone()
        joint_vel = robot.data.default_joint_vel[env_ids].clone()
        robot.write_joint_state_to_sim(joint_pos, joint_vel, env_ids=env_ids)
        robot.set_joint_position_target(joint_pos, env_ids=env_ids)
        self.actions[env_ids] = joint_pos
        # Permute cubes across the 3 fixed slots on each reset
        if len(env_ids) > 0:
            mdp.randomize_cubes_permutation(
                self,
                env_ids,
                cube_names=self.cfg.cube_names,
            )
