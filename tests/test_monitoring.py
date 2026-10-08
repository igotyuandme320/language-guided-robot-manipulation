"""A lost grasp requires sustained separation while the skill needs a grasp."""

import unittest

from execution.monitoring import GraspMonitor


class GraspMonitorTests(unittest.TestCase):
    def test_sustained_separation_reports_loss(self):
        monitor = GraspMonitor()
        for _ in range(9):
            self.assertFalse(monitor.update(0.08, True, 0.01))
        self.assertTrue(monitor.update(0.08, True, 0.01))

    def test_brief_separation_does_not_accumulate_across_recovery(self):
        monitor = GraspMonitor()
        self.assertFalse(monitor.update(0.08, True, 0.06))
        self.assertFalse(monitor.update(0.02, True, 0.01))
        self.assertFalse(monitor.update(0.08, True, 0.06))

    def test_intentional_release_disables_and_resets_the_check(self):
        monitor = GraspMonitor()
        self.assertFalse(monitor.update(0.08, True, 0.06))
        self.assertFalse(monitor.update(0.20, False, 1.0))
        self.assertFalse(monitor.update(0.08, True, 0.06))

    def test_invalid_measurements_are_not_counted(self):
        monitor = GraspMonitor()
        for distance, dt in ((float("nan"), 0.01), (float("inf"), 0.01), (-0.01, 0.01),
                             (0.08, 0), (0.08, float("nan"))):
            with self.subTest(distance=distance, dt=dt):
                with self.assertRaises(ValueError):
                    monitor.update(distance, True, dt)

    def test_invalid_thresholds_are_rejected(self):
        for options in ({"distance_threshold": 0}, {"duration": -1}, {"duration": float("inf")}):
            with self.subTest(options=options):
                with self.assertRaises(ValueError):
                    GraspMonitor(**options)


if __name__ == "__main__":
    unittest.main()
