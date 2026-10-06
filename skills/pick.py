from enum import Enum, auto

import torch


class PickPhase(Enum):
    REST = auto()
    APPROACH_ABOVE = auto()
    APPROACH_OBJECT = auto()
    GRASP = auto()
    LIFT = auto()


class PickSkill:
    def __init__(
        self,
        hover_height: float = 0.10,
        position_threshold: float = 0.01,
    ):
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

    def step(
        self,
        ee_position,
        object_position,
        lift_position,
        dt,
    ):
        self.wait_time += dt

        if self.phase == PickPhase.REST:
            target_position = ee_position.clone()
            gripper_closed = False

            if self.wait_time >= 0.2:
                self.phase = PickPhase.APPROACH_ABOVE
                self.wait_time = 0.0

        elif self.phase == PickPhase.APPROACH_ABOVE:
            target_position = object_position.clone()
            target_position[2] += self.hover_height
            gripper_closed = False

            if self._close_enough(ee_position, target_position):
                if self.wait_time >= 0.5:
                    self.phase = PickPhase.APPROACH_OBJECT
                    self.wait_time = 0.0

        elif self.phase == PickPhase.APPROACH_OBJECT:
            target_position = object_position.clone()
            gripper_closed = False

            if self._close_enough(ee_position, target_position):
                if self.wait_time >= 0.6:
                    self.phase = PickPhase.GRASP
                    self.wait_time = 0.0

        elif self.phase == PickPhase.GRASP:
            target_position = object_position.clone()
            gripper_closed = True

            if self.wait_time >= 0.3:
                self.phase = PickPhase.LIFT
                self.wait_time = 0.0

        elif self.phase == PickPhase.LIFT:
            target_position = lift_position.clone()
            gripper_closed = True

        return target_position, gripper_closed
