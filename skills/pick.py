from enum import Enum, auto
import math

import torch


class PickPhase(Enum):
    REST = auto()
    APPROACH_ABOVE = auto()
    APPROACH_OBJECT = auto()
    GRASP = auto()
    LIFT = auto()


class PickSkill:
    """Return a TCP position target and gripper command for one Panda.

    The caller provides observed positions in a common frame and handles IK.
    LIFT is a commanded phase; it is not proof that the object was grasped.
    """
    def __init__(
        self,
        hover_height: float = 0.10,
        position_threshold: float = 0.01,
    ):
        if not math.isfinite(hover_height) or hover_height <= 0:
            raise ValueError("hover_height must be positive and finite")
        if not math.isfinite(position_threshold) or position_threshold <= 0:
            raise ValueError("position_threshold must be positive and finite")
        self.hover_height = hover_height
        self.position_threshold = position_threshold
        self.phase = PickPhase.REST
        self.wait_time = 0.0

    def reset(self):
        self.phase = PickPhase.REST
        self.wait_time = 0.0

    def _close_enough(self, current_position, target_position):
        distance = torch.linalg.norm(current_position - target_position)
        return distance.item() < self.position_threshold

    def _wait_at_target(self, current_position, target_position, dt, duration):
        # Only uninterrupted time near the target counts as settling time.
        if self._close_enough(current_position, target_position):
            self.wait_time += dt
        else:
            self.wait_time = 0.0
        return self.wait_time >= duration

    def step(
        self,
        ee_position,
        object_position,
        lift_position,
        dt,
    ):
        if not math.isfinite(dt) or dt <= 0:
            raise ValueError("dt must be positive and finite")
        positions = torch.stack((ee_position, object_position, lift_position))
        if positions.shape != (3, 3) or not torch.isfinite(positions).all():
            raise ValueError("positions must be finite 3D vectors for one robot")

        if self.phase == PickPhase.REST:
            self.wait_time += dt
            target_position = ee_position.clone()
            gripper_closed = False

            if self.wait_time >= 0.2:
                self.phase = PickPhase.APPROACH_ABOVE
                self.wait_time = 0.0

        elif self.phase == PickPhase.APPROACH_ABOVE:
            target_position = object_position.clone()
            target_position[2] += self.hover_height
            gripper_closed = False

            if self._wait_at_target(ee_position, target_position, dt, 0.5):
                self.phase = PickPhase.APPROACH_OBJECT
                self.wait_time = 0.0

        elif self.phase == PickPhase.APPROACH_OBJECT:
            target_position = object_position.clone()
            gripper_closed = False

            if self._wait_at_target(ee_position, target_position, dt, 0.6):
                self.phase = PickPhase.GRASP
                self.wait_time = 0.0

        elif self.phase == PickPhase.GRASP:
            self.wait_time += dt
            target_position = object_position.clone()
            gripper_closed = True

            if self.wait_time >= 0.3:
                self.phase = PickPhase.LIFT
                self.wait_time = 0.0

        elif self.phase == PickPhase.LIFT:
            target_position = lift_position.clone()
            gripper_closed = True

        return target_position, gripper_closed
