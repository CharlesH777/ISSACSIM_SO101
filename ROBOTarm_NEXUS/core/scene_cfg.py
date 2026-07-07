"""Scene configuration: table + 3 cubes + dual cameras + lights.

All geometry is built from Isaac Lab primitive shapes (CuboidCfg) — **no
external scene USD required**.  Only the SO101 robot USD is needed.
"""
from __future__ import annotations

import isaaclab.sim as sim_utils
from isaaclab.assets import AssetBaseCfg, ArticulationCfg, RigidObjectCfg
from isaaclab.scene import InteractiveSceneCfg
from isaaclab.sensors import FrameTransformerCfg, OffsetCfg, TiledCameraCfg
from isaaclab.utils import configclass

from .robot_cfg import SO101_FOLLOWER_CFG

# ---------------------------------------------------------------------------
#  Geometry constants
# ---------------------------------------------------------------------------
TABLE_CENTER = (-0.02, -0.42, 0.405)
TABLE_SIZE = (0.85, 0.72, 0.04)
TABLE_LEG_SIZE = (0.06, 0.06, 0.365)
WORKSPACE_SIZE = (1.80, 1.40, 0.02)

ROBOT_BASE_POS = (TABLE_CENTER[0], TABLE_CENTER[1] + 0.12, 0.395)
ROBOT_BASE_ROT = (1.0, 0.0, 0.0, 0.0)

CUBE_SIZE = 0.03  # 3 cm
CUBE_HALF = CUBE_SIZE * 0.5

# Tabletop surface Z (top of table)
TABLE_SURFACE_Z = TABLE_CENTER[2] + TABLE_SIZE[2] * 0.5  # 0.425
CUBE_SURFACE_Z = TABLE_SURFACE_Z + CUBE_HALF  # 0.44

# Three cubes placed in a row in front of the robot
CUBE_DEFAULT_POSITIONS = [
    (-0.10, -0.49, CUBE_SURFACE_Z),   # red
    (0.00, -0.49, CUBE_SURFACE_Z),    # green
    (0.10, -0.49, CUBE_SURFACE_Z),    # blue
]

TARGET_ZONE_POS = (0.26, -0.34, 0.4265)
TARGET_ZONE_WHITE_SIZE = (0.10, 0.10, 0.002)
TARGET_ZONE_BORDER_SIZE = (0.12, 0.12, 0.001)

CUBE_COLORS = {
    "red": (0.85, 0.15, 0.15),
    "green": (0.15, 0.80, 0.25),
    "blue": (0.15, 0.35, 0.85),
}


# ---------------------------------------------------------------------------
#  Helper factories
# ---------------------------------------------------------------------------
def _make_table_part(
    name: str,
    size: tuple[float, float, float],
    pos: tuple[float, float, float],
) -> RigidObjectCfg:
    return RigidObjectCfg(
        prim_path=f"{{ENV_REGEX_NS}}/{name}",
        spawn=sim_utils.CuboidCfg(
            size=size,
            rigid_props=sim_utils.RigidBodyPropertiesCfg(kinematic_enabled=True),
            collision_props=sim_utils.CollisionPropertiesCfg(
                collision_enabled=True,
                contact_offset=0.005,
                rest_offset=0.0,
            ),
            physics_material=sim_utils.RigidBodyMaterialCfg(
                static_friction=1.1, dynamic_friction=0.9
            ),
            visual_material=sim_utils.PreviewSurfaceCfg(
                diffuse_color=(0.82, 0.74, 0.62), roughness=0.50
            ),
        ),
        init_state=RigidObjectCfg.InitialStateCfg(pos=pos),
    )


def _make_cube(
    name: str,
    color: tuple[float, float, float],
    pos: tuple[float, float, float],
) -> RigidObjectCfg:
    return RigidObjectCfg(
        prim_path=f"{{ENV_REGEX_NS}}/{name}",
        spawn=sim_utils.CuboidCfg(
            size=(CUBE_SIZE, CUBE_SIZE, CUBE_SIZE),
            rigid_props=sim_utils.RigidBodyPropertiesCfg(
                kinematic_enabled=False,
                disable_gravity=False,
                solver_position_iteration_count=16,
                solver_velocity_iteration_count=1,
                # Cap velocities so a bad contact can't fling the cube away.
                # Matches leisaac generalization_table constants.
                max_linear_velocity=1000.0,
                max_angular_velocity=1000.0,
                max_depenetration_velocity=5.0,
            ),
            collision_props=sim_utils.CollisionPropertiesCfg(
                collision_enabled=True,
                contact_offset=0.005,
                rest_offset=0.0,
            ),
            physics_material=sim_utils.RigidBodyMaterialCfg(
                static_friction=0.65, dynamic_friction=0.55
            ),
            visual_material=sim_utils.PreviewSurfaceCfg(
                diffuse_color=color, roughness=0.35, metallic=0.02
            ),
        ),
        init_state=RigidObjectCfg.InitialStateCfg(pos=pos),
    )


def _make_target_zone_cfg() -> tuple[RigidObjectCfg, RigidObjectCfg]:
    """Create the original white target area with a black border."""
    border_cfg = RigidObjectCfg(
        prim_path="{ENV_REGEX_NS}/TargetZoneBorder",
        spawn=sim_utils.CuboidCfg(
            size=TARGET_ZONE_BORDER_SIZE,
            rigid_props=sim_utils.RigidBodyPropertiesCfg(kinematic_enabled=True),
            collision_props=sim_utils.CollisionPropertiesCfg(collision_enabled=False),
            visual_material_path="surface_material",
            visual_material=sim_utils.PreviewSurfaceCfg(
                diffuse_color=(0.05, 0.05, 0.05),
                roughness=0.50,
            ),
        ),
        init_state=RigidObjectCfg.InitialStateCfg(
            pos=(TARGET_ZONE_POS[0], TARGET_ZONE_POS[1], TARGET_ZONE_POS[2] - 0.0005),
        ),
    )
    zone_cfg = RigidObjectCfg(
        prim_path="{ENV_REGEX_NS}/TargetZone",
        spawn=sim_utils.CuboidCfg(
            size=TARGET_ZONE_WHITE_SIZE,
            rigid_props=sim_utils.RigidBodyPropertiesCfg(kinematic_enabled=True),
            collision_props=sim_utils.CollisionPropertiesCfg(collision_enabled=False),
            visual_material_path="surface_material",
            visual_material=sim_utils.PreviewSurfaceCfg(
                diffuse_color=(0.98, 0.98, 0.98),
                roughness=0.25,
            ),
        ),
        init_state=RigidObjectCfg.InitialStateCfg(pos=TARGET_ZONE_POS),
    )
    return border_cfg, zone_cfg


_TARGET_ZONE_BORDER_CFG: RigidObjectCfg
_TARGET_ZONE_CFG: RigidObjectCfg
_TARGET_ZONE_BORDER_CFG, _TARGET_ZONE_CFG = _make_target_zone_cfg()


# ---------------------------------------------------------------------------
#  Scene
# ---------------------------------------------------------------------------
@configclass
class SO101MinimalSceneCfg(InteractiveSceneCfg):
    """Minimal scene: SO101 + table + 3 cubes + dual cameras."""

    # --- workspace floor ------------------------------------------------
    scene: RigidObjectCfg = RigidObjectCfg(
        prim_path="{ENV_REGEX_NS}/Scene",
        spawn=sim_utils.CuboidCfg(
            size=WORKSPACE_SIZE,
            rigid_props=sim_utils.RigidBodyPropertiesCfg(kinematic_enabled=True),
            collision_props=sim_utils.CollisionPropertiesCfg(
                collision_enabled=True,
                contact_offset=0.005,
                rest_offset=0.0,
            ),
            physics_material=sim_utils.RigidBodyMaterialCfg(
                static_friction=1.0, dynamic_friction=0.8
            ),
            visual_material=sim_utils.PreviewSurfaceCfg(
                diffuse_color=(0.56, 0.56, 0.54), roughness=0.96
            ),
        ),
        init_state=RigidObjectCfg.InitialStateCfg(pos=(0.0, -0.35, 0.01)),
    )

    # --- robot ----------------------------------------------------------
    robot: ArticulationCfg = SO101_FOLLOWER_CFG.replace(
        prim_path="{ENV_REGEX_NS}/Robot"
    )

    # --- end-effector frame (for IK / observation) ----------------------
    ee_frame: FrameTransformerCfg = FrameTransformerCfg(
        prim_path="{ENV_REGEX_NS}/Robot/base",
        debug_vis=False,
        target_frames=[
            FrameTransformerCfg.FrameCfg(
                prim_path="{ENV_REGEX_NS}/Robot/gripper",
                name="gripper",
            ),
            FrameTransformerCfg.FrameCfg(
                prim_path="{ENV_REGEX_NS}/Robot/jaw",
                name="jaw",
                offset=OffsetCfg(pos=(-0.021, -0.070, 0.02)),
            ),
        ],
    )

    # --- table ----------------------------------------------------------
    table_top: RigidObjectCfg = _make_table_part(
        "TableTop", TABLE_SIZE, TABLE_CENTER
    )
    table_leg_fl: RigidObjectCfg = _make_table_part(
        "TableLegFL", TABLE_LEG_SIZE,
        (TABLE_CENTER[0] - 0.36, TABLE_CENTER[1] - 0.28, 0.202),
    )
    table_leg_fr: RigidObjectCfg = _make_table_part(
        "TableLegFR", TABLE_LEG_SIZE,
        (TABLE_CENTER[0] + 0.36, TABLE_CENTER[1] - 0.28, 0.202),
    )
    table_leg_rl: RigidObjectCfg = _make_table_part(
        "TableLegRL", TABLE_LEG_SIZE,
        (TABLE_CENTER[0] - 0.36, TABLE_CENTER[1] + 0.28, 0.202),
    )
    table_leg_rr: RigidObjectCfg = _make_table_part(
        "TableLegRR", TABLE_LEG_SIZE,
        (TABLE_CENTER[0] + 0.36, TABLE_CENTER[1] + 0.28, 0.202),
    )

    # --- three cubes ----------------------------------------------------
    cube_red: RigidObjectCfg = _make_cube(
        "CubeRed", CUBE_COLORS["red"], CUBE_DEFAULT_POSITIONS[0]
    )
    cube_green: RigidObjectCfg = _make_cube(
        "CubeGreen", CUBE_COLORS["green"], CUBE_DEFAULT_POSITIONS[1]
    )
    cube_blue: RigidObjectCfg = _make_cube(
        "CubeBlue", CUBE_COLORS["blue"], CUBE_DEFAULT_POSITIONS[2]
    )
    target_zone_border: RigidObjectCfg = _TARGET_ZONE_BORDER_CFG
    target_zone: RigidObjectCfg = _TARGET_ZONE_CFG

    # --- front camera (overhead view of the tabletop) -------------------
    front: TiledCameraCfg = TiledCameraCfg(
        prim_path="{ENV_REGEX_NS}/Robot/base/front_camera",
        offset=TiledCameraCfg.OffsetCfg(
            pos=(0.0, -0.45, 0.6),
            rot=(0.1650476, -0.9862856, 0.0, 0.0),
            convention="ros",
        ),  # wxyz
        data_types=["rgb"],
        spawn=sim_utils.PinholeCameraCfg(
            focal_length=28.7,
            focus_distance=400.0,
            horizontal_aperture=38.11,
            clipping_range=(0.01, 50.0),
            lock_camera=True,
        ),
        width=640,
        height=480,
        update_period=1 / 30.0,
    )

    # --- wrist camera (mounted on the gripper) --------------------------
    wrist: TiledCameraCfg = TiledCameraCfg(
        prim_path="{ENV_REGEX_NS}/Robot/gripper/wrist_camera",
        offset=TiledCameraCfg.OffsetCfg(
            pos=(-0.001, 0.1, -0.04),
            rot=(-0.404379, -0.912179, -0.0451242, 0.0486914),
            convention="ros",
        ),
        data_types=["rgb"],
        spawn=sim_utils.PinholeCameraCfg(
            focal_length=36.5,
            focus_distance=400.0,
            horizontal_aperture=36.83,
            clipping_range=(0.01, 50.0),
            lock_camera=True,
        ),
        width=640,
        height=480,
        update_period=1 / 30.0,
    )

    # --- lighting -------------------------------------------------------
    sun_light: AssetBaseCfg = AssetBaseCfg(
        prim_path="{ENV_REGEX_NS}/SunLight",
        spawn=sim_utils.DistantLightCfg(
            color=(1.0, 1.0, 1.0),
            enable_color_temperature=True,
            color_temperature=5000.0,
            # Match GeneralizationTableSimpleEnvCfg: 950 (not 1100)
            intensity=950.0,
            angle=0.9,
        ),
        init_state=AssetBaseCfg.InitialStateCfg(pos=(0.0, 0.0, 2.5)),
    )

    sky_light: AssetBaseCfg = AssetBaseCfg(
        prim_path="{ENV_REGEX_NS}/SkyLight",
        spawn=sim_utils.DomeLightCfg(
            color=(1.0, 1.0, 1.0),
            enable_color_temperature=True,
            color_temperature=6000.0,
            # Match GeneralizationTableSimpleEnvCfg: 45 (not 55)
            intensity=45.0,
            visible_in_primary_ray=False,
        ),
    )
