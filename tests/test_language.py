"""Strict language matching prevents partially executing unsupported requests."""
import unittest

from planning.language import parse_instruction


class LanguageTests(unittest.TestCase):
    def test_pick_phrases(self):
        for text in (
            "pick up the red cube", "Lift the red block.", "Please grab the red cube!",
            "拿起红色方块", "请抓起红色方块。",
        ):
            with self.subTest(text=text):
                self.assertEqual(parse_instruction(text).to_dict(), {
                    "action": "pick", "object": "red_cube", "target": None,
                })

    def test_place_phrases(self):
        for text in (
            "put the red cube on the green platform", "Place red block onto green target.",
            "请把红色方块放到绿色平台上。", "将红色方块放在绿色平台上",
        ):
            with self.subTest(text=text):
                self.assertEqual(parse_instruction(text).to_dict(), {
                    "action": "place", "object": "red_cube", "target": "green_platform",
                })

    def test_whitespace_case_and_fullwidth_text_are_normalized(self):
        goal = parse_instruction("  ＰＬＥＡＳＥ   PUT the RED cube ON the GREEN platform！  ")
        self.assertEqual(goal.action, "place")
        self.assertEqual(goal.target, "green_platform")

    def test_negation_unknown_entities_and_compound_requests_are_rejected(self):
        for text in (
            "", "move it", "pick the blue cube", "pick up the cube", "pick up the green platform",
            "do not pick up the red cube", "don't lift the red cube", "不要拿起红色方块",
            "put the red cube on the blue platform", "put red cube under green platform",
            "pick up the red cube and drop it", "拿起红色方块然后扔掉",
            "put the red cube on the green platform and then pick it up",
        ):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_instruction(text)


if __name__ == "__main__":
    unittest.main()
