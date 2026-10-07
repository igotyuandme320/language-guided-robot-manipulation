"""Behavior checks for the single-arm pick skill; no simulator required."""
import unittest

import torch

from skills.pick import PickPhase, PickSkill


class PickSkillTests(unittest.TestCase):
    def setUp(self):
        self.skill = PickSkill()
        self.object = torch.tensor([0.5, 0.0, 0.02])
        self.hover = torch.tensor([0.5, 0.0, 0.12])
        self.lift = torch.tensor([0.5, 0.0, 0.22])
        self.far = torch.tensor([0.1, 0.0, 0.4])

    def step(self, ee, dt):
        return self.skill.step(ee, self.object, self.lift, dt)

    def test_pick_sequence_and_gripper_commands(self):
        target, closed = self.step(self.far, 0.2)
        self.assertFalse(closed)
        self.assertEqual(self.skill.phase, PickPhase.APPROACH_ABOVE)
        target, closed = self.step(self.hover, 0.5)
        torch.testing.assert_close(target, self.hover)
        self.assertFalse(closed)
        self.assertEqual(self.skill.phase, PickPhase.APPROACH_OBJECT)
        self.step(self.object, 0.6)
        self.assertEqual(self.skill.phase, PickPhase.GRASP)
        _, closed = self.step(self.object, 0.3)
        self.assertTrue(closed)
        self.assertEqual(self.skill.phase, PickPhase.LIFT)
        target, closed = self.step(self.object, 0.1)
        torch.testing.assert_close(target, torch.tensor([0.5, 0.0, 0.22]))
        self.assertTrue(closed)

    def test_hover_wait_counts_only_continuous_time_near_target(self):
        self.step(self.far, 0.2)
        self.step(self.far, 10.0)
        self.step(self.hover, 0.1)
        self.assertEqual(self.skill.phase, PickPhase.APPROACH_ABOVE)
        self.step(self.far, 1.0)
        self.step(self.hover, 0.4)
        self.assertEqual(self.skill.phase, PickPhase.APPROACH_ABOVE)
        self.step(self.hover, 0.2)
        self.assertEqual(self.skill.phase, PickPhase.APPROACH_OBJECT)

    def test_object_wait_does_not_count_travel_time(self):
        self.step(self.far, 0.2)
        self.step(self.hover, 0.5)
        self.step(self.far, 10.0)
        self.step(self.object, 0.1)
        self.assertEqual(self.skill.phase, PickPhase.APPROACH_OBJECT)

    def test_invalid_dt_is_rejected_without_advancing(self):
        for dt in (0.0, -0.1, float("nan"), float("inf")):
            with self.subTest(dt=dt), self.assertRaises(ValueError):
                self.step(self.far, dt)
        self.assertEqual(self.skill.phase, PickPhase.REST)
        self.assertEqual(self.skill.wait_time, 0.0)

    def test_invalid_configuration_is_rejected(self):
        for kwargs in ({"hover_height": 0.0}, {"position_threshold": -0.01}, {"hover_height": float("nan")}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                PickSkill(**kwargs)

    def test_nonfinite_pose_is_rejected(self):
        invalid = torch.tensor([float("nan"), 0.0, 0.0])
        with self.assertRaises(ValueError):
            self.step(invalid, 0.1)
        self.assertEqual(self.skill.wait_time, 0.0)

    def test_reset_returns_to_open_gripper_rest(self):
        self.step(self.far, 0.2)
        self.step(self.hover, 0.5)
        self.step(self.object, 0.6)
        self.step(self.object, 0.3)
        self.skill.reset()
        _, closed = self.step(self.far, 0.1)
        self.assertEqual(self.skill.phase, PickPhase.REST)
        self.assertFalse(closed)


if __name__ == "__main__":
    unittest.main()
