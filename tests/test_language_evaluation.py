"""Schema rejection is not the same as a correct semantic refusal."""

import unittest

from scripts.day6_evaluate import score_guarded_output, score_model_output

PICK = {"action": "pick", "object": "red_cube", "target": None}
PLACE = {"action": "place", "object": "red_cube", "target": "green_platform"}
PICK_OUTPUT = '{"status":"ok","goal":{"action":"pick","object":"red_cube","target":null}}'


class LanguageEvaluationTests(unittest.TestCase):
    def test_guard_blocks_negation_even_when_model_accepts(self):
        row = score_guarded_output("Do not lift the red cube.", PICK_OUTPUT, None)
        self.assertEqual((row["status"], row["source"], row["correct"]), ("rejected", "guard", True))

    def test_guard_does_not_rewrite_wrong_final_action(self):
        row = score_guarded_output("Move the red cube onto the green platform.", PICK_OUTPUT, PLACE)
        self.assertEqual(row["status"], "rejected")
        self.assertFalse(row["correct"])

    def test_known_template_uses_rules_without_claiming_model_credit(self):
        row = score_guarded_output("pick up the red cube", "not JSON", PICK)
        self.assertEqual((row["source"], row["goal"], row["correct"]), ("rules", PICK, True))

    def test_novel_supported_request_still_needs_valid_model_output(self):
        row = score_guarded_output("Please hold the red cube.", "not JSON", PICK)
        self.assertEqual(row["status"], "invalid_output")
        self.assertFalse(row["correct"])

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
