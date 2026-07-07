"""SO101 Follower robot configuration — standalone, no leisaac dependency.

The USD asset path is resolved in this order:
  1. ``SO101_USD_PATH`` environment variable
  2. ``ROBOTarm_NEXUS/assets/robots/so101_follower.usd`` (bundled copy)
  3. ``ROBOTarm_NEXUS/assets/so101_follower.usd`` (legacy fallback)
  4. The original leisaac assets directory (auto-detected from sibling
     projects or ancestor workspace roots)

Joint limits, motor limits, and rest-pose ranges are duplicated here so the
package has **zero** import-time dependency on ``leisaac``.
"""
from __future__ import annotations

import math
import os
from pathlib import Path

import isaaclab.sim as sim_utils
from isaaclab.actuators import ImplicitActuatorCfg
from isaaclab.assets.articulation import ArticulationCfg

from .specs import ACTIVE_ROBOT

# ---------------------------------------------------------------------------
#  USD asset path resolution
# ---------------------------------------------------------------------------
_CORE_ROOT = Path(__file__).resolve().parent
_PKG_ROOT = _CORE_ROOT.parent


def _resolve_usd_path() -> str:
    """Locate so101_follower.usd without depending on leisaac."""
    # 1) explicit env override
    env_path = os.environ.get(ACTIVE_ROBOT.usd_env_var, "")
    if env_path:
        return str(Path(env_path).expanduser().resolve())

    # 2) bundled copy inside this package
    bundled = _PKG_ROOT / "assets" / "robots" / ACTIVE_ROBOT.bundled_usd_filename
    if bundled.is_file():
        return str(bundled)

    # 3) legacy flat asset location kept for backward compatibility
    legacy_bundled = _PKG_ROOT / "assets" / ACTIVE_ROBOT.bundled_usd_filename
    if legacy_bundled.is_file():
        return str(legacy_bundled)

    # 4) auto-detect the original leisaac assets dir from this repo root or
    #    any ancestor workspace root that contains sibling projects.
    search_roots = [_PKG_ROOT.parent, *_PKG_ROOT.parents]
    seen_roots: set[Path] = set()
    for search_root in search_roots:
        if search_root in seen_roots or not search_root.is_dir():
            continue
        seen_roots.add(search_root)
        for pattern in ACTIVE_ROBOT.usd_search_patterns:
            for candidate in search_root.glob(pattern):
                if candidate.is_file():
                    return str(candidate.resolve())

    raise FileNotFoundError(
        f"Cannot find {ACTIVE_ROBOT.bundled_usd_filename}. Set {ACTIVE_ROBOT.usd_env_var} "
        f"or place the USD at ROBOTarm_NEXUS/assets/robots/{ACTIVE_ROBOT.bundled_usd_filename}"
    )


ROBOT_USD_PATH = _resolve_usd_path()

# ---------------------------------------------------------------------------
#  Articulation configuration
# ---------------------------------------------------------------------------
ROBOT_CFG = ArticulationCfg(
    spawn=sim_utils.UsdFileCfg(
        usd_path=ROBOT_USD_PATH,
        rigid_props=sim_utils.RigidBodyPropertiesCfg(
            # Match leisaac IK / state-machine mode: disable gravity on the
            # robot so the real-servo PD gains (stiffness=17.8, damping=0.60)
            # can hold the arm still.  With gravity enabled these low gains
            # cannot hold the arm and it enters a sustained limit-cycle
            # oscillation (joint_vel ≈ 0.15 rad/s, never decays).  The real
            # SO101 firmware has gravity compensation; in sim we emulate that
            # by turning gravity off for the articulation.  Cubes are still
            # affected by gravity normally.
            disable_gravity=True,
        ),
        articulation_props=sim_utils.ArticulationRootPropertiesCfg(
            enabled_self_collisions=True,
            solver_position_iteration_count=4,
            solver_velocity_iteration_count=4,
            fix_root_link=True,
        ),
    ),
    init_state=ArticulationCfg.InitialStateCfg(
        pos=(0.0, -0.30, 0.395),
        rot=(1.0, 0.0, 0.0, 0.0),
        # Match leisaac lerobot.py: all-zero joint pose.  With
        # disable_gravity=True the arm holds this pose without oscillation.
        joint_pos={
            name: 0.0 for name in ACTIVE_ROBOT.joint_names
        },
    ),
    actuators={
        ACTIVE_ROBOT.actuator_gripper_name: ImplicitActuatorCfg(
            joint_names_expr=[ACTIVE_ROBOT.gripper_joint_name],
            effort_limit_sim=10,
            velocity_limit_sim=10,
            # Match leisaac STS3215 real servo PD gains.  Higher stiffness
            # (e.g. 80) makes the arm over-stiff and transfers huge contact
            # forces into the cubes, causing visible jitter on grasp/contact.
            stiffness=17.8,
            damping=0.60,
        ),
        ACTIVE_ROBOT.actuator_arm_name: ImplicitActuatorCfg(
            joint_names_expr=list(ACTIVE_ROBOT.arm_joint_names),
            effort_limit_sim=10,
            velocity_limit_sim=10,
            stiffness=17.8,
            damping=0.60,
        ),
    },
    soft_joint_pos_limit_factor=1.0,
)

# ---------------------------------------------------------------------------
#  Joint limits (degrees, as written in the USD)
# ---------------------------------------------------------------------------
ROBOT_USD_JOINT_LIMITS = {
    "shoulder_pan": (-110.0, 110.0),
    "shoulder_lift": (-100.0, 100.0),
    "elbow_flex": (-100.0, 90.0),
    "wrist_flex": (-95.0, 95.0),
    "wrist_roll": (-160.0, 160.0),
    "gripper": (-10.0, 100.0),
}

# Motor limits on the real device (normalized -100~100)
ROBOT_MOTOR_LIMITS = {
    "shoulder_pan": (-100.0, 100.0),
    "shoulder_lift": (-100.0, 100.0),
    "elbow_flex": (-100.0, 100.0),
    "wrist_flex": (-100.0, 100.0),
    "wrist_roll": (-100.0, 100.0),
    "gripper": (0.0, 100.0),
}

# Rest-pose detection ranges (degrees)
ROBOT_REST_POSE_RANGE = {
    "shoulder_pan": (-30.0, 30.0),
    "shoulder_lift": (-130.0, -70.0),
    "elbow_flex": (60.0, 120.0),
    "wrist_flex": (20.0, 80.0),
    "wrist_roll": (-30.0, 30.0),
    "gripper": (-40.0, 20.0),
}

JOINT_NAMES = list(ACTIVE_ROBOT.joint_names)

# Backward-compatible aliases kept for existing imports and notes.
SO101_FOLLOWER_USD_PATH = ROBOT_USD_PATH
SO101_FOLLOWER_CFG = ROBOT_CFG
SO101_FOLLOWER_USD_JOINT_LIMITS = ROBOT_USD_JOINT_LIMITS
SO101_FOLLOWER_MOTOR_LIMITS = ROBOT_MOTOR_LIMITS
SO101_FOLLOWER_REST_POSE_RANGE = ROBOT_REST_POSE_RANGE
