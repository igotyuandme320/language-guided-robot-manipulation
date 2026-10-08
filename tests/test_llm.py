"""A model can propose a goal, but only the small validated domain is executable."""

import json
import unittest

from planning.llm import RejectedInstruction, parse_model_output


class ModelOutputTests(unittest.TestCase):
    def test_supported_pick_and_place_outputs_become_goals(self):
        for goal in (
            {"action": "pick", "object": "red_cube", "target": None},
            {"action": "place", "object": "red_cube", "target": "green_platform"},
        ):
            with self.subTest(goal=goal):
                output = json.dumps({"status": "ok", "goal": goal})
                self.assertEqual(parse_model_output(output).to_dict(), goal)

    def test_explicit_rejection_is_distinct_from_malformed_output(self):
        with self.assertRaises(RejectedInstruction):
            parse_model_output('{"status":"reject","reason":"No blue cube exists."}')
        for output in ('{"status":"reject"}', '{"status":"reject","reason":null}',
                       '{"status":"reject","reason":""}'):
            with self.subTest(output=output):
                with self.assertRaises(ValueError) as context:
                    parse_model_output(output)
                self.assertNotIsInstance(context.exception, RejectedInstruction)

    def test_unknown_objects_targets_and_actions_are_not_executable(self):
        for goal in (
            {"action": "pick", "object": "blue_cube", "target": None},
            {"action": "place", "object": "red_cube", "target": "blue_platform"},
            {"action": "throw", "object": "red_cube", "target": None},
            {"action": "pick", "object": "red_cube", "target": "green_platform"},
            {"action": "place", "object": "red_cube", "target": None},
        ):
            with self.subTest(goal=goal):
                with self.assertRaises(ValueError):
                    parse_model_output(json.dumps({"status": "ok", "goal": goal}))

    def test_extra_or_missing_fields_are_not_silently_ignored(self):
        for output in (
            '{"status":"ok","goal":{"action":"pick","object":"red_cube"}}',
            '{"status":"ok","goal":{"action":"pick","object":"red_cube","target":null,"speed":100}}',
            '{"status":"ok","goal":{"action":"pick","object":"red_cube","target":null},"plan":["throw"]}',
            '{"status":"reject","reason":"unknown","goal":null}',
        ):
            with self.subTest(output=output):
                with self.assertRaises(ValueError):
                    parse_model_output(output)

    def test_whole_output_must_be_unambiguous_json(self):
        for output in (
            'Here is the goal: {"status":"reject","reason":"unknown"}',
            '```json\n{"status":"reject","reason":"unknown"}\n```',
            '{"status":"ok","status":"reject","reason":"unknown"}',
            '{"status":"ok","goal":{"action":"pick","object":"blue_cube","object":"red_cube","target":null}}',
            '[{"status":"reject","reason":"unknown"}]',
            '{"status":"ok","goal":null}',
            '{"status":"ok","goal":{"action":NaN,"object":"red_cube","target":null}}',
        ):
            with self.subTest(output=output):
                with self.assertRaises(ValueError):
                    parse_model_output(output)


if __name__ == "__main__":
    unittest.main()
