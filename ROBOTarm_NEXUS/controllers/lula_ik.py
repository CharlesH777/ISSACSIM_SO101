"""SO101 IK controller — standalone, extracted from leisaac.

Provides two IK backends:

1. **Manual DLS** (``compute_action``): 3-DOF planar damped-least-squares
   for the side-view Pygame panel.  Controls (reach, z, tool_angle) →
   (shoulder_lift, elbow_flex, wrist_flex).

2. **Official Lula** (``compute_action_to_world_position``): Isaac Sim's
   ``LulaKinematicsSolver.compute_inverse_kinematics`` with
   ``target_orientation=None`` — position-only IK that perfectly fits the
   5-DOF SO101 arm.  Iterates to a 5 mm position tolerance with no
   steady-state offset (unlike RMPFlow).

The bundled Lula assets (URDF + YAMLs) live under
``ROBOTarm_NEXUS/assets/ik/lula/``.
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path

import isaaclab.utils.math as math_utils
import numpy as np
import torch

from ..core.robot_cfg import (
    SO101_FOLLOWER_REST_POSE_RANGE,
    SO101_FOLLOWER_USD_JOINT_LIMITS,
)

# ---------------------------------------------------------------------------
#  Lula asset paths (bundled in this package)
# ---------------------------------------------------------------------------
_PKG_ROOT = Path(__file__).resolve().parent.parent
_LULA_ASSET_DIR = _PKG_ROOT / "assets" / "ik" / "lula"
_LULA_URDF = _LULA_ASSET_DIR / "so101_rmpflow.urdf"
_LULA_DESCRIPTOR = _LULA_ASSET_DIR / "so101_robot_description.yaml"


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------
def _rest_pose_center_rad() -> dict[str, float]:
    return {
        name: math.radians((lo + hi) * 0.5)
        for name, (lo, hi) in SO101_FOLLOWER_REST_POSE_RANGE.items()
    }


def _joint_limit_rad(joint_name: str) -> tuple[float, float]:
    lo, hi = SO101_FOLLOWER_USD_JOINT_LIMITS[joint_name]
    return math.radians(lo), math.radians(hi)


def _wrap_to_pi(angle: float) -> float:
    return math.atan2(math.sin(angle), math.cos(angle))


def _read_local_ee_pose(env):
    """EE pose in the robot base frame."""
    robot = env.scene["robot"]
    ee_frame = env.scene["ee_frame"]
    ee_pos_w = ee_frame.data.target_pos_w[:, 0, :]
    ee_quat_w = ee_frame.data.target_quat_w[:, 0, :]
    return math_utils.subtract_frame_transforms(
        robot.data.root_pos_w, robot.data.root_quat_w, ee_pos_w, ee_quat_w
    )


# ---------------------------------------------------------------------------
#  Dataclasses
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class PlanarEeFeedback:
    """Side-view panel feedback (read-only)."""
    reach: float
    z: float
    tool_angle: float
    wrist_roll: float
    arm_points: list[tuple[float, float]]


@dataclass(slots=True)
class PlanarPanelIKConfig:
    """Tuning parameters for the manual DLS IK and action smoothing."""
    reach_min: float = 0.12
    reach_max: float = 0.58
    z_min: float = 0.02
    z_max: float = 0.42
    damping: float = 0.10
    position_gain: float = 5.0
    orientation_gain: float = 2.5
    posture_weight: float = 0.08
    orientation_weight: float = 1.0
    max_joint_delta: float = 0.05
    action_blend: float = 0.45
    gripper_open_pos: float = 1.0
    gripper_close_pos: float | None = None
    desired_tool_angle: float = math.pi


# ---------------------------------------------------------------------------
#  Controller
# ---------------------------------------------------------------------------
class PlanarSideViewJointController:
    """Dual-backend IK controller for the SO101 arm.

    Manual mode: ``compute_action()`` — 3-DOF planar DLS.
    Auto mode:   ``compute_action_to_world_position()`` — Lula position-only.
    """

    _JOINT_ORDER = (
        "shoulder_pan", "shoulder_lift", "elbow_flex",
        "wrist_flex", "wrist_roll", "gripper",
    )
    _PLANAR_JOINTS = ("shoulder_lift", "elbow_flex", "wrist_flex")
    _ARM_JACOBIAN_JOINTS = (
        "shoulder_pan", "shoulder_lift", "elbow_flex",
        "wrist_flex", "wrist_roll",
    )
    _AUTO_WRIST_ROLL_NOMINAL_RAD = -math.pi * 0.5

    def __init__(self, env, config: PlanarPanelIKConfig | None = None):
        self._env = env
        self._robot = env.scene["robot"]
        self._device = env.device
        self._config = config or PlanarPanelIKConfig()
        self._ee_body_idx = self._robot.find_bodies("gripper")[0][0]
        self._joint_ids = {
            name: self._robot.joint_names.index(name)
            for name in self._JOINT_ORDER
        }
        self._planar_joint_ids = [
            self._joint_ids[n] for n in self._PLANAR_JOINTS
        ]
        self._jacobian_joint_ids = [
            self._joint_ids[n] for n in self._ARM_JACOBIAN_JOINTS
        ]
        self._planar_jacobian_columns = [1, 2, 3]
        self._joint_lower = torch.tensor(
            [_joint_limit_rad(n)[0] for n in self._PLANAR_JOINTS],
            device=self._device, dtype=torch.float32,
        )
        self._joint_upper = torch.tensor(
            [_joint_limit_rad(n)[1] for n in self._PLANAR_JOINTS],
            device=self._device, dtype=torch.float32,
        )
        self._rest_pose = _rest_pose_center_rad()
        self._preferred_planar_joint_pos = torch.tensor(
            [self._rest_pose[n] for n in self._PLANAR_JOINTS],
            device=self._device, dtype=torch.float32,
        )
        self._target_wrist_roll = float(self._rest_pose["wrist_roll"])
        gripper_lower, _ = _joint_limit_rad("gripper")
        self._gripper_open_pos = float(self._config.gripper_open_pos)
        self._gripper_close_pos = (
            gripper_lower
            if self._config.gripper_close_pos is None
            else float(self._config.gripper_close_pos)
        )
        self._tool_axis_index = 2
        self._tool_axis_sign = -1.0
        self._panel_body_ids = self._resolve_panel_body_ids()
        self._single_cube_auto_wrist_roll_target = self._clamp_wrist_roll_target(
            self._AUTO_WRIST_ROLL_NOMINAL_RAD
        )

        # ---- Lula IK backend ------------------------------------------------
        self._auto_ik_joints = (
            "shoulder_pan", "shoulder_lift", "elbow_flex",
            "wrist_flex", "wrist_roll",
        )
        self._auto_ik_joint_ids = [
            self._joint_ids[n] for n in self._auto_ik_joints
        ]
        self._target_shoulder_pan = 0.0
        self._target_reach = 0.0
        self._target_z = 0.0
        self._desired_tool_angle = float(self._config.desired_tool_angle)
        self._last_arm_target = None

        try:
            from isaacsim.core.utils.extensions import enable_extension
            enable_extension("isaacsim.robot_motion.lula")
            enable_extension("isaacsim.robot_motion.motion_generation")
            from isaacsim.robot_motion.motion_generation.lula.kinematics import (
                LulaKinematicsSolver,
            )
            self._lula_ik_solver = LulaKinematicsSolver(
                robot_description_path=str(_LULA_DESCRIPTOR),
                urdf_path=str(_LULA_URDF),
            )
            self._lula_ik_frame = "gripper"
            self._lula_joint_names = list(self._lula_ik_solver.get_joint_names())
            self._lula_output_to_action_slot = {
                out_idx: self._joint_ids[name]
                for out_idx, name in enumerate(self._lula_joint_names)
                if name in self._joint_ids
            }
            self._sync_lula_base_pose()
        except Exception as exc:
            raise RuntimeError(
                "SO101 IK requires IsaacSim Lula kinematics; "
                f"failed to initialize: {exc}"
            ) from exc

        self._debug_ik = os.environ.get(
            "SO101_DEBUG_IK", ""
        ) not in ("", "0", "false", "False")
        self.reset_targets_from_current_pose()

    # -- properties -------------------------------------------------------
    @property
    def config(self) -> PlanarPanelIKConfig:
        return self._config

    @property
    def target_reach(self) -> float:
        return self._target_reach

    @property
    def target_z(self) -> float:
        return self._target_z

    @property
    def target_shoulder_pan(self) -> float:
        return self._target_shoulder_pan

    @property
    def target_tool_angle(self) -> float:
        return self._desired_tool_angle

    @property
    def target_wrist_roll(self) -> float:
        return self._target_wrist_roll

    @property
    def auto_ik_backend(self) -> str:
        return "isaacsim_lula_kinematics"

    # -- wrist roll management -------------------------------------------
    def wrist_roll_limits(self) -> tuple[float, float]:
        return _joint_limit_rad("wrist_roll")

    def default_single_cube_auto_wrist_roll_target(self) -> float:
        return self._clamp_wrist_roll_target(self._AUTO_WRIST_ROLL_NOMINAL_RAD)

    def single_cube_auto_wrist_roll_target(self) -> float:
        return float(self._single_cube_auto_wrist_roll_target)

    def set_single_cube_auto_wrist_roll_target(
        self, target_radians: float | None = None
    ) -> None:
        if target_radians is None:
            target_radians = self._AUTO_WRIST_ROLL_NOMINAL_RAD
        self._single_cube_auto_wrist_roll_target = self._clamp_wrist_roll_target(
            float(target_radians)
        )

    def set_wrist_roll_target(self, target_radians: float) -> None:
        self._target_wrist_roll = self._clamp_wrist_roll_target(float(target_radians))

    def nudge_wrist_roll(self, delta_radians: float) -> None:
        self.set_wrist_roll_target(self._target_wrist_roll + float(delta_radians))

    # -- target management ------------------------------------------------
    def reset_targets_from_current_pose(self) -> PlanarEeFeedback:
        feedback = self.read_feedback()
        joint_pos = self._robot.data.joint_pos[0]
        self._target_shoulder_pan = float(
            joint_pos[self._joint_ids["shoulder_pan"]].item()
        )
        self._target_wrist_roll = float(
            joint_pos[self._joint_ids["wrist_roll"]].item()
        )
        self._target_reach = feedback.reach
        self._target_z = feedback.z
        self._last_arm_target = None
        return feedback

    def set_target(self, target_reach: float, target_z: float) -> None:
        self._target_reach = min(
            self._config.reach_max,
            max(self._config.reach_min, float(target_reach)),
        )
        self._target_z = min(
            self._config.z_max,
            max(self._config.z_min, float(target_z)),
        )

    def set_normalized_target(self, x_alpha: float, z_alpha: float) -> None:
        x_alpha = min(1.0, max(0.0, float(x_alpha)))
        z_alpha = min(1.0, max(0.0, float(z_alpha)))
        self.set_target(
            self._config.reach_min
            + x_alpha * (self._config.reach_max - self._config.reach_min),
            self._config.z_min
            + z_alpha * (self._config.z_max - self._config.z_min),
        )

    def update_shoulder_pan(self, delta_command: float, dt: float) -> None:
        lower, upper = _joint_limit_rad("shoulder_pan")
        self._target_shoulder_pan = min(
            upper,
            max(lower, self._target_shoulder_pan + float(delta_command) * dt),
        )

    def nudge_shoulder_pan(self, delta_radians: float) -> None:
        lower, upper = _joint_limit_rad("shoulder_pan")
        self._target_shoulder_pan = min(
            upper,
            max(lower, self._target_shoulder_pan + float(delta_radians)),
        )

    def set_shoulder_pan_target(self, target_radians: float) -> None:
        lower, upper = _joint_limit_rad("shoulder_pan")
        self._target_shoulder_pan = min(upper, max(lower, float(target_radians)))

    # -- read feedback ----------------------------------------------------
    def read_feedback(self) -> PlanarEeFeedback:
        ee_pos_local, ee_quat_local = _read_local_ee_pose(self._env)
        ee_rot_local = math_utils.matrix_from_quat(ee_quat_local)[0]
        tool_axis = ee_rot_local[:, self._tool_axis_index] * float(self._tool_axis_sign)
        tool_angle = math.atan2(
            float(tool_axis[1].item()), float(tool_axis[2].item())
        )
        return PlanarEeFeedback(
            reach=float((-ee_pos_local[0, 1]).item()),
            z=float(ee_pos_local[0, 2].item()),
            tool_angle=tool_angle,
            wrist_roll=float(
                self._robot.data.joint_pos[0, self._joint_ids["wrist_roll"]].item()
            ),
            arm_points=self._read_arm_points(),
        )

    # ------------------------------------------------------------------
    #  Backend 1: manual DLS IK (side-view panel mode)
    # ------------------------------------------------------------------
    def compute_action(self, grip_closed: bool) -> tuple[torch.Tensor, PlanarEeFeedback]:
        feedback = self.read_feedback()
        joint_pos = self._robot.data.joint_pos[0]
        planar_joint_pos = joint_pos[self._planar_joint_ids]
        jacobian_local = self._compute_local_jacobian()
        planar_jacobian = jacobian_local[:, self._planar_jacobian_columns]

        task_jacobian = torch.stack(
            (
                -planar_jacobian[1],
                planar_jacobian[2],
                -float(self._config.orientation_weight) * planar_jacobian[3],
            ),
            dim=0,
        )
        task_error = torch.tensor(
            (
                (self._target_reach - feedback.reach) * float(self._config.position_gain),
                (self._target_z - feedback.z) * float(self._config.position_gain),
                _wrap_to_pi(self._desired_tool_angle - feedback.tool_angle)
                * float(self._config.orientation_gain),
            ),
            device=self._device,
            dtype=torch.float32,
        )

        posture_weight = float(self._config.posture_weight)
        posture_jacobian = posture_weight * torch.eye(
            3, device=self._device, dtype=torch.float32
        )
        posture_error = posture_weight * (
            self._preferred_planar_joint_pos - planar_joint_pos
        )
        augmented_jacobian = torch.cat((task_jacobian, posture_jacobian), dim=0)
        augmented_error = torch.cat((task_error, posture_error), dim=0)

        damping = float(self._config.damping)
        normal_matrix = augmented_jacobian.T @ augmented_jacobian + (
            damping ** 2
        ) * torch.eye(3, device=self._device, dtype=torch.float32)
        rhs = augmented_jacobian.T @ augmented_error
        delta_joint = torch.linalg.solve(normal_matrix, rhs)
        delta_joint = torch.clamp(
            delta_joint,
            min=-float(self._config.max_joint_delta),
            max=float(self._config.max_joint_delta),
        )

        next_planar_joint_pos = torch.clamp(
            planar_joint_pos + delta_joint,
            min=self._joint_lower,
            max=self._joint_upper,
        )
        action = torch.zeros(
            (1, len(self._JOINT_ORDER)), device=self._device, dtype=torch.float32
        )
        action[0, 0] = float(self._target_shoulder_pan)
        action[0, 1:4] = next_planar_joint_pos
        action[0, 4] = self._target_wrist_roll
        action[0, 5] = (
            self._gripper_close_pos if grip_closed else self._gripper_open_pos
        )

        blend = min(1.0, max(0.0, float(self._config.action_blend)))
        if self._last_arm_target is not None:
            action[:, :5] = self._last_arm_target[:, :5] + blend * (
                action[:, :5] - self._last_arm_target[:, :5]
            )
        self._last_arm_target = action[:, :5].clone()
        return action, feedback

    # ------------------------------------------------------------------
    #  Backend 2: official Lula position-only IK
    # ------------------------------------------------------------------
    def _sync_lula_base_pose(self) -> None:
        """Tell Lula where the robot base is in world coordinates."""
        root_pos_w = self._robot.data.root_pos_w[0].detach().cpu().numpy()
        root_quat_w = self._robot.data.root_quat_w[0].detach().cpu().numpy()
        self._lula_ik_solver.set_robot_base_pose(
            robot_position=root_pos_w,
            robot_orientation=root_quat_w,
        )

    def compute_action_to_world_position(
        self,
        target_pos_w: torch.Tensor,
        target_quat_w: torch.Tensor,
        grip_closed: bool,
    ) -> tuple[torch.Tensor, PlanarEeFeedback]:
        """Drive the gripper to a world-space position via Lula IK.

        ``target_orientation=None`` → position-only solve (5-DOF compatible).
        """
        feedback = self.read_feedback()
        self._sync_lula_base_pose()

        target_pos_np = target_pos_w.detach().cpu().numpy().reshape(3)

        # warm-start from current joint angles for continuity
        joint_pos = self._robot.data.joint_pos[0]
        warm_start = np.array(
            [
                float(joint_pos[self._joint_ids[name]].item())
                for name in self._lula_joint_names
            ],
            dtype=np.float64,
        )

        cspace_position, success = self._lula_ik_solver.compute_inverse_kinematics(
            frame_name=self._lula_ik_frame,
            target_position=target_pos_np,
            target_orientation=None,  # position-only
            warm_start=warm_start,
            position_tolerance=0.005,
        )

        action = torch.zeros(
            (1, len(self._JOINT_ORDER)), device=self._device, dtype=torch.float32
        )
        if success and cspace_position is not None:
            joint_pos_des = torch.tensor(
                cspace_position, device=self._device, dtype=torch.float32
            )
            for out_idx, action_slot in self._lula_output_to_action_slot.items():
                action[0, action_slot] = joint_pos_des[out_idx]
        else:
            for name in self._auto_ik_joints:
                action[0, self._joint_ids[name]] = joint_pos[self._joint_ids[name]]

        action[0, self._joint_ids["wrist_roll"]] = (
            self.single_cube_auto_wrist_roll_target()
        )
        action[0, 5] = (
            self._gripper_close_pos if grip_closed else self._gripper_open_pos
        )

        if self._debug_ik:
            current_pos_w = self._robot.data.body_pos_w[
                0, self._ee_body_idx
            ].clone()
            raw_err_m = float(
                torch.linalg.norm(target_pos_w - current_pos_w).item()
            )
            print(
                f"[IK] success={bool(success)} "
                f"err={raw_err_m * 100:.2f}cm "
                f"target=({target_pos_np[0]:.3f},"
                f"{target_pos_np[1]:.3f},{target_pos_np[2]:.3f})"
            )

        blend = min(1.0, max(0.0, float(self._config.action_blend)))
        if self._last_arm_target is not None:
            action[:, :5] = self._last_arm_target[:, :5] + blend * (
                action[:, :5] - self._last_arm_target[:, :5]
            )
        action[0, self._joint_ids["wrist_roll"]] = (
            self.single_cube_auto_wrist_roll_target()
        )
        self._last_arm_target = action[:, :5].clone()

        # Sync side-view panel coordinates
        root_pos_w = self._robot.data.root_pos_w
        root_quat_w = self._robot.data.root_quat_w
        target_pos_local = math_utils.quat_apply(
            math_utils.quat_inv(root_quat_w),
            target_pos_w.reshape(1, 3) - root_pos_w,
        )[0]
        self._target_shoulder_pan = float(action[0, 0].item())
        self._target_reach = float((-target_pos_local[1]).item())
        self._target_z = float(target_pos_local[2].item())
        return action, feedback

    # ------------------------------------------------------------------
    #  Internal helpers
    # ------------------------------------------------------------------
    def _compute_local_jacobian(self) -> torch.Tensor:
        jacobian_world = self._robot.root_physx_view.get_jacobians()[
            :, self._ee_body_idx - 1, :, self._jacobian_joint_ids
        ]
        root_rot_matrix = math_utils.matrix_from_quat(
            math_utils.quat_inv(self._robot.data.root_quat_w)
        )
        jacobian_local = jacobian_world.clone()
        jacobian_local[:, :3, :] = torch.bmm(
            root_rot_matrix, jacobian_local[:, :3, :]
        )
        jacobian_local[:, 3:, :] = torch.bmm(
            root_rot_matrix, jacobian_local[:, 3:, :]
        )
        return jacobian_local[0]

    def _resolve_panel_body_ids(self) -> list[int]:
        body_names = [n.lower() for n in self._robot.body_names]
        selected: list[int] = []
        seen: set[int] = set()
        for token in ("base", "shoulder", "elbow", "wrist", "gripper"):
            for bid, bname in enumerate(body_names):
                if token in bname and bid not in seen:
                    selected.append(bid)
                    seen.add(bid)
                    break
        if self._ee_body_idx not in seen:
            selected.append(self._ee_body_idx)
        return selected

    def _read_arm_points(self) -> list[tuple[float, float]]:
        if not self._panel_body_ids:
            return []
        root_pos = self._robot.data.root_pos_w
        root_quat = self._robot.data.root_quat_w
        root_rot = math_utils.matrix_from_quat(math_utils.quat_inv(root_quat))
        body_pos_w = self._robot.data.body_pos_w[:, self._panel_body_ids, :]
        relative = body_pos_w - root_pos.unsqueeze(1)
        local = torch.bmm(
            root_rot, torch.transpose(relative, 1, 2)
        ).transpose(1, 2)[0]
        return [
            (float((-p[1]).item()), float(p[2].item())) for p in local
        ]

    def _clamp_wrist_roll_target(self, target_radians: float) -> float:
        lower, upper = self.wrist_roll_limits()
        return min(upper, max(lower, float(target_radians)))
