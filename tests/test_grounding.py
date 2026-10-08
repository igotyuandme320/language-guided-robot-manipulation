"""Initial symbolic support must follow measured position and settling."""
import unittest

from planning.grounding import observe_initial_state


class GroundingTests(unittest.TestCase):
    def setUp(self):
        self.platform = (0.5, -0.22, 0.04)
        self.still = (0, 0, 0, 0, 0, 0)

    def test_settled_table_cube_is_on_table(self):
        state = observe_initial_state((0.5, 0.0, 0.017), self.still, self.platform)
        self.assertEqual(state.cube_location, "table")

    def test_settled_platform_cube_is_on_platform(self):
        state = observe_initial_state((0.5002, -0.2195, 0.04), self.still, self.platform)
        self.assertEqual(state.cube_location, "green_platform")

    def test_height_alone_does_not_identify_the_platform(self):
        with self.assertRaises(ValueError):
            observe_initial_state((0.5, 0.0, 0.04), self.still, self.platform)

    def test_airborne_or_nonfinite_cube_is_rejected(self):
        for position in ((0.5, 0, 0.2), (float("nan"), 0, 0.02)):
            with self.subTest(position=position), self.assertRaises(ValueError):
                observe_initial_state(position, self.still, self.platform)

    def test_moving_cube_is_not_treated_as_settled(self):
        for velocity in ((0, 0, 0.2, 0, 0, 0), (0, 0, 0, 0.2, 0, 0), (0, 0, 0, float("nan"), 0, 0)):
            with self.subTest(velocity=velocity), self.assertRaises(ValueError):
                observe_initial_state((0.5, 0, 0.017), velocity, self.platform)


if __name__ == "__main__":
    unittest.main()
