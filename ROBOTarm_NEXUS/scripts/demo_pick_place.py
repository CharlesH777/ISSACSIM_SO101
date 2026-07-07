"""Demo: enable both cameras, grasp one cube with Lula IK, and place it."""

from __future__ import annotations

import argparse
import gc

from isaaclab.app import AppLauncher
from ROBOTarm_NEXUS.core.specs import CUBE_NAMES, DEFAULT_PLACE_TARGET_W, ENV_ID

parser = argparse.ArgumentParser(
    description="ROBOTarm_NEXUS demo — dual cameras + Lula IK pick and place"
)
parser.add_argument(
    "--cube",
    choices=CUBE_NAMES,
    default=CUBE_NAMES[0],
    help="Cube to pick and place",
)
parser.add_argument(
    "--place",
    type=float,
    nargs=3,
    metavar=("X", "Y", "Z"),
    default=DEFAULT_PLACE_TARGET_W,
    help="World-space cube-center goal position in meters",
)
parser.add_argument(
    "--steps",
    type=int,
    default=90,
    help="Legacy extra control budget; original Lula phase durations stay fixed",
)
parser.add_argument(
    "--no_cameras",
    action="store_true",
    help="Disable cameras for debugging; by default the demo enables front+wrist cameras",
)
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
if not args_cli.no_cameras:
    args_cli.enable_cameras = True

from .common import close_sim_app, dynamic_reset_gripper_effort_limit_sim, open_camera_viewports, validate_camera_device  # noqa: E402

validate_camera_device(args_cli, parser)

app_launcher = AppLauncher(vars(args_cli))
simulation_app = app_launcher.app

import gymnasium as gym  # noqa: E402
import torch  # noqa: E402

import ROBOTarm_NEXUS  # noqa: F401, E402
from ROBOTarm_NEXUS.controllers import PlanarPanelIKConfig, PlanarSideViewJointController  # noqa: E402
from isaaclab_tasks.utils import parse_env_cfg  # noqa: E402

from .common import strip_cameras  # noqa: E402
from .grasping_common import (  # noqa: E402
    current_grasp_point_world,
    current_gripper_target_world,
    grasp_target_to_gripper_target,
    load_ee_calibration,
    scripted_env_step,
    select_wrist_roll_target,
    smoothstep,
)

CLEARANCE_Z = 0.12
AUTO_PHASE_ORDER = (
    "approach",
    "descend",
    "grasp",
    "lift",
    "transport",
    "place",
    "release",
    "retreat",
    "done",
)
AUTO_PHASE_DURATIONS = {
    "approach": 50,
    "descend": 30,
    "grasp": 15,
    "lift": 35,
    "transport": 70,
    "place": 30,
    "release": 15,
    "retreat": 35,
    "done": 0,
}
AUTO_PHASE_MAX_STEPS = {
    "approach": 180,
    "descend": 140,
    "grasp": 20,
    "lift": 160,
    "transport": 220,
    "place": 140,
    "release": 20,
    "retreat": 180,
    "done": 0,
}
AUTO_GRIP_CLOSED_PHASES = {"grasp", "lift", "transport", "place"}
AUTO_MOTION_PHASES = {"approach", "descend", "lift", "transport", "place", "retreat"}
AUTO_TARGET_REACHED_TOLERANCE_M = 0.012
GRASP_DROP_TOL_M = 0.090
LIFT_SUCCESS_M = 0.05
FINAL_PLACE_TOL_M = 0.050


def report_camera_streams(obs_policy: dict[str, torch.Tensor]) -> None:
    """Print camera tensor status so the demo clearly shows both streams are live."""
    print("  Camera streams:")
    for cam_name in ("front", "wrist"):
        tensor = obs_policy.get(cam_name)
        if tensor is None:
            print(f"    {cam_name:8s} disabled")
            continue
        print(f"    {cam_name:8s} shape={tuple(tensor.shape)} dtype={tensor.dtype}")


def run_pick_and_place_demo(
    env,
    ik: PlanarSideViewJointController,
    cube_name: str,
    grasp_point_in_gripper: torch.Tensor,
    nominal_wrist_roll: float,
    place_target_w: torch.Tensor,
    steps: int,
) -> None:
    """Run the original Lula auto-pick phase machine against a fixed place target."""
    cube = env.scene[cube_name]
    cube_pos_start = cube.data.root_pos_w[0].clone()
    print(f"\n--- demo target: {cube_name} ---")
    print(
        f"  pick from: ({cube_pos_start[0]:.3f}, {cube_pos_start[1]:.3f}, {cube_pos_start[2]:.3f})"
    )
    print(
        f"  place to : ({place_target_w[0]:.3f}, {place_target_w[1]:.3f}, {place_target_w[2]:.3f})"
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
        above_place = place_target_w.clone()
        above_place[2] = place_target_w[2] + CLEARANCE_Z
        at_place = place_target_w.clone()

        if auto_phase_start_jaw_w is None or auto_phase_end_jaw_w is None:
            start = current_grasp_w
            phase_targets = {
                "approach": above_cube,
                "descend": at_cube,
                "grasp": start,
                "lift": above_cube,
                "transport": above_place,
                "place": at_place,
                "release": start,
                "retreat": above_place,
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
                f"  Phase {auto_phase:8s} → "
                f"({auto_phase_end_jaw_w[0]:.3f}, {auto_phase_end_jaw_w[1]:.3f}, {auto_phase_end_jaw_w[2]:.3f})"
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
        scripted_env_step(env, action, phase_name=auto_phase, context="pick/place")
        peak_lifted = max(peak_lifted, float((cube.data.root_pos_w[0, 2] - cube_pos_start[2]).item()))

        if auto_phase in {"lift", "transport", "place"}:
            grasp_pt_next = current_grasp_point_world(env, grasp_point_in_gripper)
            cube_pos_next = cube.data.root_pos_w[0].clone()
            cube_to_grasp = float(torch.linalg.norm(grasp_pt_next - cube_pos_next).item())
            if cube_to_grasp > GRASP_DROP_TOL_M:
                raise RuntimeError(f"{auto_phase}: lost the cube during physical grasp transport")

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
        raise RuntimeError(f"{cube_name} did not complete the Lula auto phase machine")

    print(f"  Peak lift : {peak_lifted * 100:.1f} cm")
    if peak_lifted < LIFT_SUCCESS_M:
        raise RuntimeError(
            f"{cube_name} never reached the physical lift threshold ({peak_lifted * 100:.1f} cm)"
        )

    final_cube_pos = cube.data.root_pos_w[0].clone()
    final_err = float(torch.linalg.norm(final_cube_pos - place_target_w).item())
    print(
        f"  Final cube: ({final_cube_pos[0]:.3f}, {final_cube_pos[1]:.3f}, {final_cube_pos[2]:.3f})"
    )
    print(f"  Place err : {final_err * 100:.1f} cm")
    if final_err > FINAL_PLACE_TOL_M:
        raise RuntimeError(
            f"{cube_name} finished {final_err * 100:.1f} cm away from the target placement"
        )


def main() -> None:
    env = None
    ik = None
    camera_windows = []
    try:
        env_cfg = parse_env_cfg(
            ENV_ID,
            device=args_cli.device,
            num_envs=1,
        )
        # The scripted demo owns its own completion conditions; leaving the env
        # success threshold active causes IsaacLab to auto-reset as soon as the
        # cube is lifted, which shows up as visible twitching in the UI.
        env_cfg.lift_height_threshold = 1.0e6

        cameras_requested = bool(getattr(args_cli, "enable_cameras", False))
        if args_cli.no_cameras or not cameras_requested:
            strip_cameras(env_cfg)

        env = gym.make(ENV_ID, cfg=env_cfg)
        obs, _info = env.reset()
        env_unwrapped = env.unwrapped
        dynamic_reset_gripper_effort_limit_sim(env_unwrapped)
        if not getattr(args_cli, "headless", False):
            camera_windows = open_camera_viewports(env_unwrapped)

        print("=" * 68)
        print("ROBOTarm_NEXUS Demo — Dual Cameras + Lula IK Pick and Place")
        print("=" * 68)
        print(f"  Device: {env_unwrapped.device}")
        print(f"  Cube  : {args_cli.cube}")
        print(f"  Place : ({args_cli.place[0]:.3f}, {args_cli.place[1]:.3f}, {args_cli.place[2]:.3f})")
        report_camera_streams(obs["policy"])

        grasp_point_xyz, calibrated_wrist_roll = load_ee_calibration()
        grasp_point_in_gripper = torch.tensor(
            grasp_point_xyz,
            dtype=torch.float32,
            device=env_unwrapped.device,
        )
        place_target_w = torch.tensor(
            args_cli.place,
            dtype=torch.float32,
            device=env_unwrapped.device,
        )

        ik = PlanarSideViewJointController(env_unwrapped, PlanarPanelIKConfig())
        nominal_wrist_roll = (
            float(calibrated_wrist_roll)
            if calibrated_wrist_roll is not None
            else ik.default_single_cube_auto_wrist_roll_target()
        )

        run_pick_and_place_demo(
            env_unwrapped,
            ik,
            args_cli.cube,
            grasp_point_in_gripper=grasp_point_in_gripper,
            nominal_wrist_roll=nominal_wrist_roll,
            place_target_w=place_target_w,
            steps=args_cli.steps,
        )
        print("\nDemo complete.")
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
