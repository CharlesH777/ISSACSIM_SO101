"""Shared helpers for runnable script modules."""

from __future__ import annotations

import argparse
import os
import sys

import torch

from ..core.specs import ACTIVE_ROBOT


def validate_camera_device(args_cli, parser: argparse.ArgumentParser) -> None:
    """Reject unsupported CPU+tiled-camera combinations before Isaac Sim boots."""
    if getattr(args_cli, "enable_cameras", False) and str(args_cli.device).startswith("cpu"):
        parser.error(
            "--enable_cameras requires a CUDA device for tiled camera rendering; "
            "use --device cuda:0 or omit the flag"
        )


def strip_cameras(env_cfg) -> None:
    """Remove image sensors and matching observation metadata from the env cfg."""
    for cam_name in ("front", "wrist"):
        if hasattr(env_cfg.scene, cam_name):
            delattr(env_cfg.scene, cam_name)
        env_cfg.state_space.pop(cam_name, None)
        env_cfg.observation_space.pop(cam_name, None)
    env_cfg.cameras = []


def close_sim_app(simulation_app) -> None:
    """Terminate Isaac Sim in a way that does not hang these smoke runners.

    Isaac Sim 5.1 on this host can hang or segfault during Kit shutdown even
    after the environment logic has completed successfully. The default path for
    these standalone runners is therefore:

    1. flush stdout/stderr
    2. bypass Kit shutdown
    3. force process exit via ``os._exit(0)``

    Set ``SO101_FULL_SIM_SHUTDOWN=1`` to opt back into normal
    ``simulation_app.close()`` behavior when debugging Kit shutdown itself.
    """
    full_shutdown = os.environ.get("SO101_FULL_SIM_SHUTDOWN", "")
    if full_shutdown in ("1", "true", "True", "yes", "on"):
        simulation_app.close()
        return
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)


def _resolved_camera_prim_path(env, camera_name: str, env_index: int = 0) -> str:
    """Resolve a camera sensor name to the spawned camera prim path."""
    camera_sensor = env.scene[camera_name]
    sensor_prims = getattr(camera_sensor, "_sensor_prims", ())
    if sensor_prims:
        return sensor_prims[env_index].GetPath().pathString
    env_root = env.scene.env_prim_paths[env_index]
    return camera_sensor.cfg.prim_path.replace("{ENV_REGEX_NS}", env_root)


def open_camera_viewports(env, camera_names: tuple[str, ...] = ("front", "wrist")) -> list:
    """Open dedicated GUI viewport windows for the requested camera sensors."""
    import omni.kit.commands
    from omni.kit.viewport.utility import create_viewport_window, get_active_viewport_window

    default_viewport_window = get_active_viewport_window()
    anchor_x = int(getattr(default_viewport_window, "position_x", 32))
    anchor_y = int(getattr(default_viewport_window, "position_y", 32))
    anchor_w = int(getattr(default_viewport_window, "width", 1280))

    width = 640
    height = 480
    gap = 24
    windows = []

    for index, camera_name in enumerate(camera_names):
        if camera_name not in env.scene.keys():
            continue
        camera_prim_path = _resolved_camera_prim_path(env, camera_name)
        viewport_window = create_viewport_window(
            name=f"{camera_name.title()} Camera",
            width=width,
            height=height,
            position_x=anchor_x + anchor_w + gap,
            position_y=anchor_y + index * (height + gap),
        )
        omni.kit.commands.execute(
            "SetViewportCamera",
            camera_path=camera_prim_path,
            viewport_api=viewport_window.viewport_api,
        )
        viewport_window.visible = True
        print(f"  Opened {camera_name} camera viewport on {camera_prim_path}")
        windows.append(viewport_window)

    return windows


def dynamic_reset_gripper_effort_limit_sim(env) -> None:
    """Mirror the original Lula collection path's per-reset gripper effort update."""
    robot = env.scene["robot"]
    gripper_body_idx = robot.find_bodies(ACTIVE_ROBOT.ee_frame_name)[0][0]
    gripper_joint_id = robot.joint_names.index(ACTIVE_ROBOT.gripper_joint_name)
    gripper_pos = robot.data.body_link_pos_w[:, gripper_body_idx]
    object_positions = []
    object_masses = []

    for obj in env.scene._rigid_objects.values():
        rigid_props = getattr(getattr(getattr(obj, "cfg", None), "spawn", None), "rigid_props", None)
        if rigid_props is not None and getattr(rigid_props, "kinematic_enabled", None) is True:
            continue
        object_positions.append(obj.data.body_link_pos_w[:, 0])
        object_masses.append(obj.data.default_mass.to(gripper_pos.device))

    if not object_positions:
        return

    object_positions = torch.stack(object_positions)
    object_masses = torch.stack(object_masses)
    distances = torch.sqrt(torch.sum((object_positions - gripper_pos.unsqueeze(0)) ** 2, dim=2))
    _, min_indices = torch.min(distances, dim=0)
    env_indices = torch.arange(gripper_pos.shape[0], device=min_indices.device)
    target_masses = object_masses[min_indices, env_indices, 0]
    target_effort_limits = (target_masses / 0.15).to(robot._data.joint_effort_limits.device)

    current_effort_limit_sim = robot._data.joint_effort_limits[:, -1]
    need_update = torch.abs(target_effort_limits - current_effort_limit_sim) > 0.1
    if not torch.any(need_update):
        return

    new_limits = current_effort_limit_sim.clone()
    new_limits[need_update] = target_effort_limits[need_update]
    robot.write_joint_effort_limit_to_sim(
        limits=new_limits,
        joint_ids=[gripper_joint_id for _ in range(gripper_pos.shape[0])],
    )
