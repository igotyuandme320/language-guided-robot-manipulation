"""Placement targets and release ordering, without Isaac Sim."""
import unittest

import torch

from skills.place import PlacePhase, PlaceSkill


class PlaceSkillTests(unittest.TestCase):
    def setUp(self):
        self.skill = PlaceSkill()
        self.destination = torch.tensor([0.5, -0.22, 0.04])
        self.above = torch.tensor([0.5, -0.22, 0.19])
        self.lower = torch.tensor([0.5, -0.22, 0.045])
        self.far = torch.tensor([0.5, 0.0, 0.22])

    def step(self, position, dt):
        return self.skill.step(position, self.destination, dt)

    def test_release_only_after_arriving_and_lowering(self):
        target, closed = self.step(self.far, 1.0)
        torch.testing.assert_close(target, self.above)
        self.assertTrue(closed)
        self.assertEqual(self.skill.phase, PlacePhase.TRANSIT)
        self.step(self.above, 0.3)
        self.assertEqual(self.skill.phase, PlacePhase.LOWER)
        target, closed = self.step(self.far, 1.0)
        torch.testing.assert_close(target, self.lower)
        self.assertTrue(closed)
        self.assertEqual(self.skill.phase, PlacePhase.LOWER)
        self.step(self.lower, 0.5)
        self.assertEqual(self.skill.phase, PlacePhase.RELEASE)
        _, closed = self.step(self.lower, 0.6)
        self.assertFalse(closed)
        self.assertEqual(self.skill.phase, PlacePhase.RETRACT)
        target, closed = self.step(self.above, 0.3)
        torch.testing.assert_close(target, self.above)
        self.assertFalse(closed)
        self.assertEqual(self.skill.phase, PlacePhase.DONE)

    def test_transit_requires_continuous_arrival(self):
        self.step(self.above, 0.2)
        self.step(self.far, 10.0)
        self.step(self.above, 0.2)
        self.assertEqual(self.skill.phase, PlacePhase.TRANSIT)

    def test_reset_starts_another_closed_gripper_transit(self):
        self.step(self.above, 0.3)
        self.step(self.lower, 0.5)
        self.step(self.lower, 0.6)
        self.step(self.above, 0.3)
        self.skill.reset()
        _, closed = self.step(self.far, 0.1)
        self.assertEqual(self.skill.phase, PlacePhase.TRANSIT)
        self.assertTrue(closed)

    def test_invalid_time_and_target_are_rejected(self):
        for dt in (0, -0.1, float("nan"), float("inf")):
            with self.subTest(dt=dt), self.assertRaises(ValueError):
                self.step(self.far, dt)
        with self.assertRaises(ValueError):
            self.skill.step(self.far, torch.tensor([0.5, 0, float("nan")]), 0.1)
        self.assertEqual(self.skill.wait_time, 0.0)


if __name__ == "__main__":
    unittest.main()
