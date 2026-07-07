"""Smoke test: use the Lula IK controller to reach and lift each cube."""

from __future__ import annotations

import argparse
import gc
import json
import math
from pathlib import Path

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="SO101 Minimal Sim — Lula IK test")
parser.add_argument(
    "--steps",
    type=int,
    default=150,
    help="Legacy extra control budget; original Lula phase durations stay fixed",
)
parser.add_argument(
    "--no_cameras",
    action="store_true",
    help="Disable cameras for IK validation without RTX rendering",
)
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

from .common import close_sim_app, dynamic_reset_gripper_effort_limit_sim, open_camera_viewports, validate_camera_device  # noqa: E402

validate_camera_device(args_cli, parser)

app_launcher = AppLauncher(vars(args_cli))
simulation_app = app_launcher.app

import gymnasium as gym  # noqa: E402
import isaaclab.utils.math as math_utils  # noqa: E402
import torch  # noqa: E402

import ROBOTarm_NEXUS  # noqa: F401, E402
from ROBOTarm_NEXUS.controllers import PlanarPanelIKConfig, PlanarSideViewJointController  # noqa: E402
from isaaclab_tasks.utils import parse_env_cfg  # noqa: E402

from .common import strip_cameras  # noqa: E402

CUBE_NAMES = ["cube_red", "cube_green", "cube_blue"]
CALIBRATION_FILE = Path.home() / ".config" / "so101_control" / "ee_calibration.json"
DEFAULT_GRASP_POINT_IN_GRIPPER = (0.03, 0.005, -0.055)
CLEARANCE_Z = 0.12
AUTO_PHASE_ORDER = ("approach", "descend", "grasp", "lift", "done")
AUTO_PHASE_DURATIONS = {
    "approach": 50,
    "descend": 30,
    "grasp": 15,
    "lift": 35,
    "done": 0,
}
AUTO_PHASE_MAX_STEPS = {
    "approach": 180,
    "descend": 140,
    "grasp": 20,
    "lift": 160,
    "done": 0,
}
AUTO_GRIP_CLOSED_PHASES = {"grasp", "lift"}
AUTO_MOTION_PHASES = {"approach", "descend", "lift"}
AUTO_TARGET_REACHED_TOLERANCE_M = 0.012
GRASP_DROP_TOL_M = 0.090
LIFT_SUCCESS_M = 0.05


def load_ee_calibration() -> tuple[tuple[float, float, float], float | None]:
    """Load the panel-calibrated grasp point and wrist-roll if available."""
    try:
        payload = json.loads(CALIBRATION_FILE.read_text())
    except (FileNotFoundError, ValueError, OSError):
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
    """Wrap into [-pi/2, pi/2] under 180-degree jaw symmetry."""
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
    ik: PlanarSideViewJointController, raw_target: float, reference: float
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
    ik: PlanarSideViewJointController,
    cube_name: str,
    nominal_roll: float,
) -> float:
    """Align the jaw with one of the cube edges while staying near the nominal roll."""
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


def scripted_env_step(env, action: torch.Tensor, *, phase_name: str) -> None:
    """Step the env and fail loudly if IsaacLab auto-resets during the scripted demo."""
    _obs, _reward, terminated, truncated, _extras = env.step(action)
    if bool(torch.any(terminated).item()) or bool(torch.any(truncated).item()):
        raise RuntimeError(
            f"Environment reset triggered during scripted IK phase '{phase_name}'. "
            "This usually means the env success/timeout condition is still active."
        )


def smoothstep(alpha: float) -> float:
    """Match the original Lula auto-pick trajectory interpolation."""
    return 3.0 * alpha * alpha - 2.0 * alpha * alpha * alpha


def run_cube_sequence(
    env,
    ik: PlanarSideViewJointController,
    cube_name: str,
    grasp_point_in_gripper: torch.Tensor,
    nominal_wrist_roll: float,
    steps: int = 200,
) -> None:
    """Lift one cube with the original Lula auto phase machine subset."""
    cube = env.scene[cube_name]
    cube_pos_start = cube.data.root_pos_w[0].clone()
    print(f"\n--- {cube_name} ---")
    print(
        f"  cube position: ({cube_pos_start[0]:.3f}, {cube_pos_start[1]:.3f}, {cube_pos_start[2]:.3f})"
    )

    ik.set_single_cube_auto_wrist_roll_target(
        select_wrist_roll_target(env, ik, cube_name, nominal_wrist_roll)
    )
    ik.reset_targets_from_current_pose()

    auto_phase = "approach"
    auto_phase_step = 0
    auto_phase_start_jaw_w: torch.Tensor | None = None
    auto_phase_end_jaw_w: torch.Tensor | None = None
    phase_prev: str | None = None
    peak_lifted = 0.0
    total_budget = max(sum(AUTO_PHASE_MAX_STEPS.values()), max(int(steps), 1) * len(AUTO_PHASE_ORDER))

    for _ in range(total_budget):
        if auto_phase == "done":
            break

        cube_pos_w = cube.data.root_pos_w[0].clone()
        _gripper_pos_w, gripper_quat_w = current_gripper_target_world(env)
        current_grasp_w = current_grasp_point_world(
            env, grasp_point_in_gripper, reference_quat_w=gripper_quat_w
        )

        above_cube = cube_pos_w.clone()
        above_cube[2] = cube_pos_w[2] + CLEARANCE_Z
        at_cube = cube_pos_w.clone()

        if auto_phase_start_jaw_w is None or auto_phase_end_jaw_w is None:
            start = current_grasp_w
            phase_targets = {
                "approach": above_cube,
                "descend": at_cube,
                "grasp": start,
                "lift": above_cube,
            }
            auto_phase_start_jaw_w = start
            auto_phase_end_jaw_w = phase_targets.get(auto_phase, start).clone()

        duration = max(AUTO_PHASE_DURATIONS.get(auto_phase, 1), 1)
        if duration <= 1:
            alpha = 1.0
        else:
            alpha = min(1.0, max(0.0, auto_phase_step / float(duration - 1)))
        jaw_target_w = auto_phase_start_jaw_w + (
            auto_phase_end_jaw_w - auto_phase_start_jaw_w
        ) * smoothstep(alpha)

        if auto_phase != phase_prev:
            print(
                f"  Phase {auto_phase:8s} → ({auto_phase_end_jaw_w[0]:.3f}, {auto_phase_end_jaw_w[1]:.3f}, {auto_phase_end_jaw_w[2]:.3f})"
            )
            phase_prev = auto_phase

        gripper_target_w = grasp_target_to_gripper_target(
            env, jaw_target_w, grasp_point_in_gripper, reference_quat_w=gripper_quat_w
        )
        action, _ = ik.compute_action_to_world_position(
            gripper_target_w,
            gripper_quat_w,
            grip_closed=auto_phase in AUTO_GRIP_CLOSED_PHASES,
        )
        scripted_env_step(env, action, phase_name=auto_phase)
        peak_lifted = max(peak_lifted, float((cube.data.root_pos_w[0, 2] - cube_pos_start[2]).item()))

        if auto_phase == "lift":
            grasp_pt_next = current_grasp_point_world(env, grasp_point_in_gripper)
            cube_pos_next = cube.data.root_pos_w[0].clone()
            cube_to_grasp = float(torch.linalg.norm(grasp_pt_next - cube_pos_next).item())
            if cube_to_grasp > GRASP_DROP_TOL_M:
                raise RuntimeError(f"{auto_phase}: lost the cube during physical grasp lift")

        auto_phase_step += 1
        min_steps = AUTO_PHASE_DURATIONS.get(auto_phase, 1)
        if auto_phase_step < min_steps:
            continue

        max_steps = max(min_steps, AUTO_PHASE_MAX_STEPS.get(auto_phase, min_steps))
        if auto_phase in AUTO_MOTION_PHASES:
            current_err_m = float(
                torch.linalg.norm(current_grasp_point_world(env, grasp_point_in_gripper) - auto_phase_end_jaw_w).item()
            )
            if current_err_m > AUTO_TARGET_REACHED_TOLERANCE_M and auto_phase_step < max_steps:
                continue
        elif auto_phase_step < max_steps:
            continue

        current_index = AUTO_PHASE_ORDER.index(auto_phase)
        auto_phase = AUTO_PHASE_ORDER[current_index + 1]
        auto_phase_step = 0
        auto_phase_start_jaw_w = None
        auto_phase_end_jaw_w = None
    else:
        raise RuntimeError(f"{cube_name} did not complete the Lula lift phase machine")

    cube_pos_after = cube.data.root_pos_w[0].clone()
    print(f"  Peak lift     : {peak_lifted * 100:.1f} cm")
    print(
        f"  Final cube pos: ({cube_pos_after[0]:.3f}, {cube_pos_after[1]:.3f}, {cube_pos_after[2]:.3f})"
    )
    if peak_lifted < LIFT_SUCCESS_M:
        raise RuntimeError(
            f"{cube_name} never reached the physical lift threshold ({peak_lifted * 100:.1f} cm)"
        )


def main() -> None:
    env = None
    ik = None
    camera_windows = []
    try:
        env_cfg = parse_env_cfg(
            "SO101-MinimalCube-v0",
            device=args_cli.device,
            num_envs=1,
        )
        # The scripted IK runner manages its own completion criteria; if the
        # env keeps "lifted cube = success", IsaacLab will auto-reset mid-grasp.
        env_cfg.lift_height_threshold = 1.0e6

        cameras_requested = bool(getattr(args_cli, "enable_cameras", False))
        if args_cli.no_cameras or not cameras_requested:
            strip_cameras(env_cfg)

        env = gym.make("SO101-MinimalCube-v0", cfg=env_cfg)
        env.reset()
        dynamic_reset_gripper_effort_limit_sim(env.unwrapped)
        if not getattr(args_cli, "headless", False):
            camera_windows = open_camera_viewports(env.unwrapped)

        grasp_point_xyz, calibrated_wrist_roll = load_ee_calibration()
        grasp_point_in_gripper = torch.tensor(
            grasp_point_xyz, dtype=torch.float32, device=env.unwrapped.device
        )

        ik = PlanarSideViewJointController(env.unwrapped, PlanarPanelIKConfig())
        nominal_wrist_roll = (
            float(calibrated_wrist_roll)
            if calibrated_wrist_roll is not None
            else ik.default_single_cube_auto_wrist_roll_target()
        )

        for cube_name in CUBE_NAMES:
            run_cube_sequence(
                env.unwrapped,
                ik,
                cube_name,
                grasp_point_in_gripper=grasp_point_in_gripper,
                nominal_wrist_roll=nominal_wrist_roll,
                steps=args_cli.steps,
            )
            ik.reset_targets_from_current_pose()

        print("\nDone.")
    finally:
        ik = None
        if env is not None:
            env.close()


if __name__ == "__main__":
    try:
        main()
    finally:
        gc.collect()
        close_sim_app(simulation_app)
