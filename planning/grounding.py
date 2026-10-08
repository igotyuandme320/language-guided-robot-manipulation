"""Map a settled cube's observed pose to the small symbolic scene model."""

import math

from .symbolic import WorldState


def observe_initial_state(cube_position, cube_velocity, platform_cube_center) -> WorldState:
    """Reject unsupported/unstable observations instead of assuming a table state."""
    if len(cube_position) != 3 or len(cube_velocity) != 6 or len(platform_cube_center) != 3:
        raise ValueError("Expected 3D positions and six linear/angular velocity components.")
    if not all(math.isfinite(value) for values in (cube_position, cube_velocity, platform_cube_center) for value in values):
        raise ValueError("Initial observations must be finite.")
    if math.hypot(*cube_velocity[:3]) > 0.01 or math.hypot(*cube_velocity[3:]) > 0.1:
        raise ValueError("Cube must settle before its symbolic state can be determined.")
    if (
        math.dist(cube_position[:2], platform_cube_center[:2]) < 0.04
        and abs(cube_position[2] - platform_cube_center[2]) < 0.008
    ):
        return WorldState("green_platform")
    if abs(cube_position[2] - 0.02) < 0.005:
        return WorldState("table")
    raise ValueError("Cube is not settled on a supported initial surface.")
