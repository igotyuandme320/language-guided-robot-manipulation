"""A single Panda, table, movable red cube, and fixed green platform.

Import this module after AppLauncher starts Isaac Sim. Distances are in meters.
The official table's surface and the robot base are both at z = 0.
"""

from isaaclab_physx.sim.schemas import PhysxCollisionCfg, PhysxRigidBodyCfg

import isaaclab.sim as sim_utils
from isaaclab.assets import AssetBaseCfg, RigidObjectCfg
from isaaclab.scene import InteractiveSceneCfg
from isaaclab.sim.spawners.materials.physics_materials_cfg import RigidBodyMaterialBaseCfg
from isaaclab.utils import configclass, replace
from isaaclab.utils.assets import ISAAC_NUCLEUS_DIR
from isaaclab_assets import FRANKA_PANDA_CFG

CUBE_SIZE = 0.04
PLATFORM_HEIGHT = 0.02


@configclass
class ManipulationSceneCfg(InteractiveSceneCfg):
    """Small tabletop workspace; one environment for now."""

    ground = AssetBaseCfg(
        prim_path="/World/Ground",
        spawn=sim_utils.GroundPlaneCfg(),
        init_state=AssetBaseCfg.InitialStateCfg(pos=(0.0, 0.0, -1.05)),
    )
    light = AssetBaseCfg(
        prim_path="/World/Light",
        spawn=sim_utils.DomeLightCfg(intensity=3000.0, color=(0.75, 0.75, 0.75)),
    )
    table = AssetBaseCfg(
        prim_path="{ENV_REGEX_NS}/Table",
        spawn=sim_utils.UsdFileCfg(
            usd_path=f"{ISAAC_NUCLEUS_DIR}/Props/Mounts/SeattleLabTable/table_instanceable.usd",
        ),
        init_state=AssetBaseCfg.InitialStateCfg(pos=(0.5, 0.0, 0.0), rot=(0.0, 0.0, 0.7071068, 0.7071068)),
    )
    robot = replace(FRANKA_PANDA_CFG, prim_path="{ENV_REGEX_NS}/Robot")
    cube = RigidObjectCfg(
        prim_path="{ENV_REGEX_NS}/RedCube",
        spawn=sim_utils.CuboidCfg(
            size=(CUBE_SIZE, CUBE_SIZE, CUBE_SIZE),
            rigid_props=PhysxRigidBodyCfg(
                solver_position_iteration_count=16,
                solver_velocity_iteration_count=4,
                max_depenetration_velocity=1.0,
            ),
            mass_props=sim_utils.MassPropertiesCfg(mass=0.05),
            collision_props=PhysxCollisionCfg(contact_offset=0.002, rest_offset=0.0),
            physics_material=RigidBodyMaterialBaseCfg(
                static_friction=1.0, dynamic_friction=1.0, restitution=0.0,
            ),
            visual_material=sim_utils.PreviewSurfaceCfg(diffuse_color=(0.8, 0.05, 0.05)),
        ),
        init_state=RigidObjectCfg.InitialStateCfg(pos=(0.5, 0.0, CUBE_SIZE / 2 + 0.005)),
    )
    platform = AssetBaseCfg(
        prim_path="{ENV_REGEX_NS}/GreenPlatform",
        spawn=sim_utils.CuboidCfg(
            size=(0.16, 0.16, PLATFORM_HEIGHT),
            collision_props=PhysxCollisionCfg(),
            visual_material=sim_utils.PreviewSurfaceCfg(diffuse_color=(0.05, 0.65, 0.12)),
        ),
        init_state=AssetBaseCfg.InitialStateCfg(pos=(0.5, -0.22, PLATFORM_HEIGHT / 2)),
    )
