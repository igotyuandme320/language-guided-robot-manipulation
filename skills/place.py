"""A small position-based placement skill for an already grasped cube."""

from enum import Enum, auto
import math

import torch


class PlacePhase(Enum):
    TRANSIT = auto()
    LOWER = auto()
    RELEASE = auto()
    RETRACT = auto()
    DONE = auto()


class PlaceSkill:
    """Move above the destination, lower, open the fingers, and retract.

    Destination is the desired cube center, in the same frame as the TCP.
    DONE describes the arm sequence; the caller must check the object pose.
    """

    def __init__(self):
        self.phase = PlacePhase.TRANSIT
        self.wait_time = 0.0

    def reset(self):
        self.phase = PlacePhase.TRANSIT
        self.wait_time = 0.0

    def step(self, ee_position, destination, dt):
        if not math.isfinite(dt) or dt <= 0:
            raise ValueError("dt must be positive and finite")
        positions = torch.stack((ee_position, destination))
        if positions.shape != (2, 3) or not torch.isfinite(positions).all():
            raise ValueError("positions must be finite 3D vectors for one robot")

        target = destination.clone()
        if self.phase in (PlacePhase.TRANSIT, PlacePhase.RETRACT, PlacePhase.DONE):
            target[2] += 0.15
        else:
            target[2] += 0.005  # Small clearance before opening; cube settles under gravity.
        closed = self.phase in (PlacePhase.TRANSIT, PlacePhase.LOWER)

        if self.phase == PlacePhase.DONE:
            return target, closed
        if self.phase == PlacePhase.RELEASE:
            self.wait_time += dt
            duration = 0.6
        else:
            near_target = torch.linalg.norm(ee_position - target).item() < 0.01
            self.wait_time = self.wait_time + dt if near_target else 0.0
            duration = 0.5 if self.phase == PlacePhase.LOWER else 0.3
        if self.wait_time >= duration:
            next_phase = {
                PlacePhase.TRANSIT: PlacePhase.LOWER,
                PlacePhase.LOWER: PlacePhase.RELEASE,
                PlacePhase.RELEASE: PlacePhase.RETRACT,
                PlacePhase.RETRACT: PlacePhase.DONE,
            }
            self.phase = next_phase[self.phase]
            self.wait_time = 0.0
        return target, closed
