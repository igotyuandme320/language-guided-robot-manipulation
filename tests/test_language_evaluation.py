"""Schema rejection is not the same as a correct semantic refusal."""

import unittest

from scripts.day6_evaluate import score_model_output

PICK = {"action": "pick", "object": "red_cube", "target": None}
PLACE = {"action": "place", "object": "red_cube", "target": "green_platform"}
PICK_OUTPUT = '{"status":"ok","goal":{"action":"pick","object":"red_cube","target":null}}'


class LanguageEvaluationTests(unittest.TestCase):
    def test_correct_goal_is_scored_against_expected_intent(self):
        self.assertTrue(score_model_output(PICK_OUTPUT, PICK)["correct"])
        self.assertFalse(score_model_output(PICK_OUTPUT, PLACE)["correct"])

    def test_schema_valid_but_unsupported_intent_is_false_acceptance(self):
        row = score_model_output(PICK_OUTPUT, None)
        self.assertFalse(row["correct"])
        self.assertEqual(row["status"], "accepted")

    def test_explicit_refusal_is_correct_only_for_unsupported_request(self):
        output = '{"status":"reject","reason":"No matching request."}'
        self.assertTrue(score_model_output(output, None)["correct"])
        self.assertFalse(score_model_output(output, PICK)["correct"])

    def test_malformed_output_does_not_earn_rejection_credit(self):
        row = score_model_output("not JSON", None)
        self.assertFalse(row["correct"])
        self.assertEqual(row["status"], "invalid_output")


if __name__ == "__main__":
    unittest.main()
