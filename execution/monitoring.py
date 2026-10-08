"""Small observation checks shared by the simulator executor and fast tests."""

import math


class GraspMonitor:
    """Report sustained cube/TCP separation only while a grasp is required.

    Proximity is a necessary check for this cube, not a contact/force sensor.
    """

    def __init__(self, distance_threshold=0.05, duration=0.10):
        if not all(math.isfinite(value) and value > 0 for value in (distance_threshold, duration)):
            raise ValueError("Grasp monitor thresholds must be finite and positive.")
        self.distance_threshold = distance_threshold
        self.duration = duration
        self.elapsed = 0.0

    def update(self, distance, grasp_required, dt):
        if not math.isfinite(distance) or distance < 0 or not math.isfinite(dt) or dt <= 0:
            raise ValueError("Distance must be finite/nonnegative and dt finite/positive.")
        self.elapsed = self.elapsed + dt if grasp_required and distance >= self.distance_threshold else 0.0
        return self.elapsed >= self.duration or math.isclose(self.elapsed, self.duration, rel_tol=1e-9, abs_tol=0.0)
