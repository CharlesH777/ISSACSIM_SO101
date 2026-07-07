"""Central project specs.

Start here when adapting the project to a different robot model. This file
collects the names, frame paths, asset filenames, and task-facing constants
that were previously scattered across the repo.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


ENV_ID = "SO101-MinimalCube-v0"
CUBE_NAMES = ("cube_red", "cube_green", "cube_blue")
DEFAULT_GRASP_POINT_IN_GRIPPER = (0.03, 0.005, -0.055)
DEFAULT_PLACE_TARGET_W = (0.26, -0.34, 0.4415)
CALIBRATION_FILE = Path.home() / ".config" / "so101_control" / "ee_calibration.json"


@dataclass(frozen=True, slots=True)
class RobotModelSpec:
    """Robot-coupled names and asset entry points for this package."""

    model_name: str
    usd_env_var: str
    bundled_usd_filename: str
    usd_search_patterns: tuple[str, ...]
    prim_name: str
    base_frame_name: str
    ee_frame_name: str
    jaw_frame_name: str
    jaw_frame_offset: tuple[float, float, float]
    front_camera_name: str
    wrist_camera_name: str
    joint_names: tuple[str, ...]
    arm_joint_names: tuple[str, ...]
    planar_joint_names: tuple[str, ...]
    gripper_joint_name: str
    actuator_arm_name: str
    actuator_gripper_name: str
    lula_asset_dirname: str
    lula_urdf_filename: str
    lula_descriptor_filename: str

    def robot_prim_path(self) -> str:
        return f"{{ENV_REGEX_NS}}/{self.prim_name}"

    def base_prim_path(self) -> str:
        return f"{self.robot_prim_path()}/{self.base_frame_name}"

    def ee_prim_path(self) -> str:
        return f"{self.robot_prim_path()}/{self.ee_frame_name}"

    def jaw_prim_path(self) -> str:
        return f"{self.robot_prim_path()}/{self.jaw_frame_name}"

    def front_camera_prim_path(self) -> str:
        return f"{self.base_prim_path()}/{self.front_camera_name}"

    def wrist_camera_prim_path(self) -> str:
        return f"{self.ee_prim_path()}/{self.wrist_camera_name}"

    def joint_index(self, joint_name: str) -> int:
        return self.joint_names.index(joint_name)


ACTIVE_ROBOT = RobotModelSpec(
    model_name="SO101 Follower",
    usd_env_var="SO101_USD_PATH",
    bundled_usd_filename="so101_follower.usd",
    usd_search_patterns=(
        "*/assets/robots/so101_follower.usd",
        "*/robots/so101_follower.usd",
        "*/leisaac/robots/so101_follower.usd",
    ),
    prim_name="Robot",
    base_frame_name="base",
    ee_frame_name="gripper",
    jaw_frame_name="jaw",
    jaw_frame_offset=(-0.021, -0.070, 0.02),
    front_camera_name="front_camera",
    wrist_camera_name="wrist_camera",
    joint_names=(
        "shoulder_pan",
        "shoulder_lift",
        "elbow_flex",
        "wrist_flex",
        "wrist_roll",
        "gripper",
    ),
    arm_joint_names=(
        "shoulder_pan",
        "shoulder_lift",
        "elbow_flex",
        "wrist_flex",
        "wrist_roll",
    ),
    planar_joint_names=(
        "shoulder_lift",
        "elbow_flex",
        "wrist_flex",
    ),
    gripper_joint_name="gripper",
    actuator_arm_name="sts3215-arm",
    actuator_gripper_name="sts3215-gripper",
    lula_asset_dirname="lula",
    lula_urdf_filename="so101_rmpflow.urdf",
    lula_descriptor_filename="so101_robot_description.yaml",
)
