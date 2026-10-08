"""The planner must respect gripper preconditions and actual goal state."""
import unittest

from planning.symbolic import Goal, SkillCall, WorldState, apply_skill, goal_satisfied, plan_goal


class SymbolicPlannerTests(unittest.TestCase):
    def test_table_to_platform_requires_pick_then_place(self):
        goal = Goal("place", "red_cube", "green_platform")
        calls = plan_goal(goal, WorldState("table"))
        self.assertEqual([call.to_dict() for call in calls], [
            {"skill": "pick", "object": "red_cube", "target": None},
            {"skill": "place", "object": "red_cube", "target": "green_platform"},
        ])

    def test_pick_goal_only_calls_pick(self):
        calls = plan_goal(Goal("pick", "red_cube"), WorldState("table"))
        self.assertEqual([call.skill for call in calls], ["pick"])

    def test_already_holding_only_requires_place(self):
        calls = plan_goal(Goal("place", "red_cube", "green_platform"), WorldState("gripper"))
        self.assertEqual([call.skill for call in calls], ["place"])

    def test_satisfied_goal_has_no_actions(self):
        self.assertEqual(plan_goal(Goal("pick", "red_cube"), WorldState("gripper")), [])
        self.assertEqual(plan_goal(Goal("place", "red_cube", "green_platform"), WorldState("green_platform")), [])

    def test_can_pick_from_platform(self):
        calls = plan_goal(Goal("pick", "red_cube"), WorldState("green_platform"))
        self.assertEqual([call.skill for call in calls], ["pick"])

    def test_place_without_grasp_is_rejected(self):
        with self.assertRaises(ValueError):
            apply_skill(WorldState("table"), SkillCall("place", "red_cube", "green_platform"))

    def test_effects_are_not_applied_to_invalid_actions(self):
        with self.assertRaises(ValueError):
            apply_skill(WorldState("gripper"), SkillCall("pick", "red_cube"))

    def test_symbolic_goal_checks_do_not_confuse_table_with_platform(self):
        goal = Goal("place", "red_cube", "green_platform")
        self.assertFalse(goal_satisfied(goal, WorldState("table")))
        self.assertFalse(goal_satisfied(goal, WorldState("gripper")))
        self.assertTrue(goal_satisfied(goal, WorldState("green_platform")))

    def test_invalid_goal_schema_is_rejected(self):
        for values in (
            ("throw", "red_cube", None),
            ("pick", "blue_cube", None),
            ("place", "red_cube", None),
            ("place", "red_cube", "blue_platform"),
            ("pick", "red_cube", "green_platform"),
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                Goal(*values)

    def test_invalid_state_and_skill_call_are_rejected(self):
        with self.assertRaises(ValueError):
            WorldState("unknown")
        with self.assertRaises(ValueError):
            SkillCall("release", "red_cube")

    def test_goal_serializes_to_plain_json_values(self):
        self.assertEqual(Goal("place", "red_cube", "green_platform").to_dict(), {
            "action": "place", "object": "red_cube", "target": "green_platform",
        })


if __name__ == "__main__":
    unittest.main()
