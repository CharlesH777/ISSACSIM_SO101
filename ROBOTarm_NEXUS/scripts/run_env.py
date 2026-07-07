"""Smoke test: launch the SO101 minimal environment and step it."""

from __future__ import annotations

import argparse
import gc

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="SO101 Minimal Sim — env test")
parser.add_argument("--num_envs", type=int, default=1)
parser.add_argument("--steps", type=int, default=200)
parser.add_argument(
    "--zero_action",
    action="store_true",
    help="Drive all joints toward the all-zero absolute target instead of holding the default pose",
)
parser.add_argument(
    "--no_cameras",
    action="store_true",
    help="Disable cameras to test basic scene without RTX rendering",
)
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

# Validate launcher args before Isaac Sim boots.
from .common import close_sim_app, open_camera_viewports, validate_camera_device  # noqa: E402

validate_camera_device(args_cli, parser)

app_launcher = AppLauncher(vars(args_cli))
simulation_app = app_launcher.app

import gymnasium as gym  # noqa: E402
import torch  # noqa: E402

import ROBOTarm_NEXUS  # noqa: F401, E402
from ROBOTarm_NEXUS.core.mdp import cube_positions  # noqa: E402
from ROBOTarm_NEXUS.core.specs import CUBE_NAMES, ENV_ID  # noqa: E402
from isaaclab_tasks.utils import parse_env_cfg  # noqa: E402

from .common import strip_cameras  # noqa: E402


def main() -> None:
    env = None
    camera_windows = []
    try:
        env_cfg = parse_env_cfg(
            ENV_ID,
            device=args_cli.device,
            num_envs=args_cli.num_envs,
        )

        cameras_requested = bool(getattr(args_cli, "enable_cameras", False))
        if args_cli.no_cameras or not cameras_requested:
            strip_cameras(env_cfg)

        env = gym.make(ENV_ID, cfg=env_cfg)
        env_unwrapped = env.unwrapped

        print("=" * 60)
        print("ROBOTarm_NEXUS — Environment Test")
        print("=" * 60)
        print(f"  Action space:  {env.action_space}")
        print(f"  Num envs:      {env_unwrapped.num_envs}")
        print(f"  Device:        {env_unwrapped.device}")

        obs, _info = env.reset()
        if not getattr(args_cli, "headless", False):
            camera_windows = open_camera_viewports(env_unwrapped)
        print(f"\n  Observation keys: {list(obs['policy'].keys())}")
        for key, val in obs["policy"].items():
            if hasattr(val, "shape"):
                print(f"    {key:20s} shape={tuple(val.shape)} dtype={val.dtype}")

        if args_cli.zero_action:
            print(f"\n  Stepping {args_cli.steps} frames with all-zero joint targets...")
            action_cmd = torch.zeros(args_cli.num_envs, 6, device=env_unwrapped.device)
        else:
            print(f"\n  Stepping {args_cli.steps} frames while holding the default pose...")
            action_cmd = env_unwrapped.scene["robot"].data.default_joint_pos.clone()

        for step in range(args_cli.steps):
            _obs, reward, terminated, _truncated, _info = env.step(action_cmd)
            if step % 50 == 0:
                cubes = cube_positions(env_unwrapped)
                print(
                    f"    step {step:3d}  reward={reward.item():.3f}  "
                    f"done={terminated.any().item()}  "
                    f"{CUBE_NAMES[0]}=({cubes[0,0,0]:.3f},{cubes[0,0,1]:.3f},{cubes[0,0,2]:.3f})"
                )

        print("\n  Final cube positions:")
        cubes = cube_positions(env_unwrapped)
        for i, name in enumerate(CUBE_NAMES):
            p = cubes[0, i]
            print(f"    {name:10s} ({p[0]:.3f}, {p[1]:.3f}, {p[2]:.3f})")

        success = env_unwrapped._check_success()
        print(f"\n  Success (any cube lifted): {success.item()}")
        print("\nDone.")
    finally:
        if env is not None:
            env.close()


if __name__ == "__main__":
    try:
        main()
    finally:
        gc.collect()
        close_sim_app(simulation_app)
