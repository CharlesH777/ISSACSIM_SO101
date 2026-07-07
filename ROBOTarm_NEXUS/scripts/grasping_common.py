"""Shared helpers for Lula grasp/lift/pick-place scripts."""

from __future__ import annotations

import json
import math
from typing import TYPE_CHECKING

import isaaclab.utils.math as math_utils
import torch

from ..core.specs import (
    CALIBRATION_FILE,
    DEFAULT_GRASP_POINT_IN_GRIPPER,
    DEFAULT_PLACE_TARGET_W,
)

if TYPE_CHECKING:
    from ..controllers import PlanarSideViewJointController


def load_ee_calibration() -> tuple[tuple[float, float, float], float | None]:
    """Load the calibrated grasp point and optional wrist-roll hint."""
    try:
        payload = json.loads(CALIBRATION_FILE.read_text())
    except (FileNotFoundError, OSError, ValueError):
        return DEFAULT_GRASP_POINT_IN_GRIPPER, None

    offset = DEFAULT_GRASP_POINT_IN_GRIPPER
    grasp_point = payload.get("grasp_point_in_gripper") if isinstance(payload, dict) else None
    if isinstance(grasp_point, dict) and {"x", "y", "z"} <= grasp_point.keys():
        offset = (
            float(grasp_point["x"]),
            float(grasp_point["y"]),
            float(grasp_point["z"]),
        )

    wrist_roll = None
    if isinstance(payload, dict):
        if "wrist_roll" in payload:
            wrist_roll = float(payload["wrist_roll"])
        elif isinstance(grasp_point, dict) and "roll" in grasp_point:
            wrist_roll = float(grasp_point["roll"])

    return offset, wrist_roll


def current_gripper_target_world(env) -> tuple[torch.Tensor, torch.Tensor]:
    """Return the live gripper-body pose from the ee frame transformer."""
    gripper_pos_w = env.scene["ee_frame"].data.target_pos_w[0, 0, :].clone()
    gripper_quat_w = env.scene["ee_frame"].data.target_quat_w[0, 0, :].clone()
    return gripper_pos_w, gripper_quat_w


def grasp_point_offset_world(
    env,
    grasp_point_in_gripper: torch.Tensor,
    reference_quat_w: torch.Tensor | None = None,
) -> torch.Tensor:
    """Map the calibrated grasp-point offset from gripper frame to world frame."""
    quat_w = current_gripper_target_world(env)[1] if reference_quat_w is None else reference_quat_w
    return math_utils.quat_apply(quat_w.reshape(1, 4), grasp_point_in_gripper.reshape(1, 3))[0]


def current_grasp_point_world(
    env,
    grasp_point_in_gripper: torch.Tensor,
    reference_quat_w: torch.Tensor | None = None,
) -> torch.Tensor:
    """Return the current calibrated grasp point in world coordinates."""
    gripper_pos_w, _gripper_quat_w = current_gripper_target_world(env)
    return gripper_pos_w + grasp_point_offset_world(
        env, grasp_point_in_gripper, reference_quat_w=reference_quat_w
    )


def grasp_target_to_gripper_target(
    env,
    grasp_target_w: torch.Tensor,
    grasp_point_in_gripper: torch.Tensor,
    reference_quat_w: torch.Tensor | None = None,
) -> torch.Tensor:
    """Convert a desired grasp-point target into the gripper-body target for IK."""
    return grasp_target_w - grasp_point_offset_world(
        env, grasp_point_in_gripper, reference_quat_w=reference_quat_w
    )


def wrap_parallel_jaw_angle(angle_radians: float) -> float:
    """Wrap into [-pi/2, pi/2] under 180-degree parallel-jaw symmetry."""
    return math.atan2(math.sin(2.0 * angle_radians), math.cos(2.0 * angle_radians)) * 0.5


def cube_yaw_in_base(env, cube_name: str) -> float:
    """Return cube yaw in the robot base frame."""
    _cube_pos_b, cube_quat_b = math_utils.subtract_frame_transforms(
        env.scene["robot"].data.root_pos_w,
        env.scene["robot"].data.root_quat_w,
        env.scene[cube_name].data.root_pos_w,
        env.scene[cube_name].data.root_quat_w,
    )
    cube_rot_b = math_utils.matrix_from_quat(cube_quat_b)
    return float(torch.atan2(cube_rot_b[0, 1, 0], cube_rot_b[0, 0, 0]).item())


def nearest_parallel_jaw_roll_within_limits(
    ik: "PlanarSideViewJointController", raw_target: float, reference: float
) -> float:
    """Choose the wrist-roll equivalent within limits that stays closest to nominal."""
    lower, upper = ik.wrist_roll_limits()
    candidates = [
        raw_target + float(k) * math.pi
        for k in range(-3, 4)
        if lower <= raw_target + float(k) * math.pi <= upper
    ]
    if not candidates:
        return min(upper, max(lower, raw_target))
    return min(candidates, key=lambda value: abs(value - reference))


def select_wrist_roll_target(
    env,
    ik: "PlanarSideViewJointController",
    cube_name: str,
    nominal_roll: float,
) -> float:
    """Align the jaw with one of the cube edges while staying near nominal roll."""
    cube_yaw = cube_yaw_in_base(env, cube_name)
    best_roll = nominal_roll
    best_metric: tuple[float, float] | None = None
    for raw_target in (nominal_roll + cube_yaw, nominal_roll + cube_yaw + math.pi * 0.5):
        candidate = nearest_parallel_jaw_roll_within_limits(ik, raw_target, nominal_roll)
        metric = (
            abs(wrap_parallel_jaw_angle(candidate - nominal_roll)),
            abs(candidate - nominal_roll),
        )
        if best_metric is None or metric < best_metric:
            best_metric = metric
            best_roll = candidate
    return best_roll


def scripted_env_step(
    env,
    action: torch.Tensor,
    *,
    phase_name: str,
    context: str,
) -> None:
    """Step the env and fail loudly if Isaac Lab auto-resets mid-script."""
    _obs, _reward, terminated, truncated, _extras = env.step(action)
    if bool(torch.any(terminated).item()) or bool(torch.any(truncated).item()):
        raise RuntimeError(
            f"Environment reset triggered during scripted {context} phase '{phase_name}'. "
            "This usually means the env success/timeout condition is still active."
        )


def smoothstep(alpha: float) -> float:
    """Match the original Lula auto-pick trajectory interpolation."""
    return 3.0 * alpha * alpha - 2.0 * alpha * alpha * alpha
