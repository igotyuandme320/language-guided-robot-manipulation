"""Literal domain checks stop known contradictions before any model/robot work."""

import unittest
from unittest.mock import patch

from planning.guarded_language import check_goal, check_request, infer_guarded
from planning.llm import RejectedInstruction
from planning.symbolic import Goal


class GuardedLanguageTests(unittest.TestCase):
    def test_novel_request_keeps_the_actual_model_goal_and_metadata(self):
        goal = Goal("pick", "red_cube")
        with patch("planning.guarded_language.infer_goal", return_value=(goal, {"raw_output": "actual response"})) as model:
            result, metadata = infer_guarded("Please hold the red cube.", timeout=5)
        model.assert_called_once_with("Please hold the red cube.", 5)
        self.assertEqual(result, goal)
        self.assertEqual(metadata["source"], "llm")
        self.assertEqual(metadata["model"]["raw_output"], "actual response")

    def test_model_refusal_is_not_hidden_by_rule_fallback(self):
        with patch("planning.guarded_language.infer_goal", side_effect=RejectedInstruction("model refused")):
            with self.assertRaisesRegex(RejectedInstruction, "model refused"):
                infer_guarded("Please hold the red cube.")

    def test_live_adapter_blocks_a_wrong_final_action(self):
        with patch("planning.guarded_language.infer_goal", return_value=(Goal("pick", "red_cube"), {})):
            with self.assertRaisesRegex(RejectedInstruction, "conflicts"):
                infer_guarded("Move the red cube onto the green platform.")

    def test_clear_pick_requests_keep_the_validated_model_goal(self):
        for text in ("Can you lift the red block?", "请拿起红色小方块。", "Please hold the red cube."):
            with self.subTest(text=text):
                goal = Goal("pick", "red_cube")
                self.assertEqual(check_goal(check_request(text), goal), goal)

    def test_clear_place_requests_require_the_named_destination(self):
        for text in ("Move the red cube onto the green target.", "请把红色小方块搬到绿色平台上。"):
            with self.subTest(text=text):
                goal = Goal("place", "red_cube", "green_platform")
                self.assertEqual(check_goal(check_request(text), goal), goal)

    def test_negated_or_contradictory_requests_are_rejected(self):
        for text in ("Do not lift the red cube.", "Don’t grab the red block.", "不要拿起红色方块。",
                     "Place the red cube on the green platform without lifting it."):
            with self.subTest(text=text):
                with self.assertRaises(RejectedInstruction):
                    check_request(text)

    def test_ambiguous_entities_are_not_guessed(self):
        for text in ("Put it on the green platform.", "Place the red cube there.", "把它放过去。"):
            with self.subTest(text=text):
                with self.assertRaises(RejectedInstruction):
                    check_request(text)

    def test_unknown_entities_are_not_replaced_by_available_ones(self):
        for text in ("Pick the blue cube.", "Place the red cube on the blue platform.",
                     "拿起绿色方块和红色方块。", "Place the red cube on the red platform."):
            with self.subTest(text=text):
                with self.assertRaises(RejectedInstruction):
                    check_request(text)

    def test_unsupported_actions_and_relations_are_rejected(self):
        for text in ("Roll the red cube onto the green target.", "Place the red cube beside the green platform.",
                     "Open the drawer and pick up the red cube.", "请把红色方块推到绿色平台上。"):
            with self.subTest(text=text):
                with self.assertRaises(RejectedInstruction):
                    check_request(text)

    def test_mentioning_platform_does_not_turn_a_pick_into_place(self):
        hints = check_request("Lift the red cube off the green platform.")
        self.assertEqual(check_goal(hints, Goal("pick", "red_cube")), Goal("pick", "red_cube"))
        with self.assertRaises(RejectedInstruction):
            check_goal(hints, Goal("place", "red_cube", "green_platform"))

    def test_model_pick_is_not_accepted_for_explicit_placement(self):
        hints = check_request("请先抓起红色方块，然后放在绿色平台上。")
        with self.assertRaises(RejectedInstruction):
            check_goal(hints, Goal("pick", "red_cube"))

    def test_missing_action_is_not_inferred_from_scene_names(self):
        with self.assertRaises(RejectedInstruction):
            check_request("Where is the red cube?")


if __name__ == "__main__":
    unittest.main()
