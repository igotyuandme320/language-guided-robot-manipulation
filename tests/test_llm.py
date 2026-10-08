"""A model can propose a goal, but only the small validated domain is executable."""

import json
import subprocess
import unittest
from unittest.mock import patch

from planning.llm import MODEL_ID, MODEL_REVISION, RejectedInstruction, infer_goal, parse_model_output


class WorkerResponseTests(unittest.TestCase):
    """Replace only subprocess I/O; exercise the real parent-side validation."""

    def metadata(self):
        return {"model_id": MODEL_ID, "revision": MODEL_REVISION, "device": "cpu",
                "raw_output": '{"status":"ok","goal":{"action":"pick","object":"red_cube","target":null}}',
                "inference_wall_time_s": 1.25}

    def infer_from_stdout(self, stdout):
        process = subprocess.CompletedProcess(args=["worker"], returncode=0, stdout=stdout, stderr="")
        with patch("planning.llm.subprocess.run", return_value=process):
            return infer_goal("pick up the red cube")

    def assert_invalid_worker(self, stdout):
        try:
            self.infer_from_stdout(stdout)
        except Exception as error:
            self.assertIsInstance(error, ValueError)
            self.assertNotIsInstance(error, RejectedInstruction)
            self.assertIn("worker response", str(error))
        else:
            self.fail("Invalid worker metadata produced an executable goal")

    def test_valid_worker_preserves_goal_and_metadata(self):
        for elapsed in (0, 1.25):
            with self.subTest(elapsed=elapsed):
                metadata = {**self.metadata(), "inference_wall_time_s": elapsed}
                goal, actual = self.infer_from_stdout(json.dumps(metadata))
                self.assertEqual(goal.to_dict(), {"action": "pick", "object": "red_cube", "target": None})
                self.assertEqual(actual, metadata)

    def test_nonobject_and_missing_fields_are_worker_errors(self):
        for metadata in (None, [], "text", {}, {"raw_output": self.metadata()["raw_output"]}):
            with self.subTest(metadata=metadata):
                self.assert_invalid_worker(json.dumps(metadata))

    def test_unexpected_worker_fields_or_identity_are_rejected(self):
        for change in ({"extra": True}, {"model_id": "another-model"}, {"revision": "unpinned"}, {"device": "cuda"}):
            with self.subTest(change=change):
                self.assert_invalid_worker(json.dumps({**self.metadata(), **change}))

    def test_worker_raw_output_must_be_text(self):
        for value in (None, {}, 7):
            with self.subTest(value=value):
                self.assert_invalid_worker(json.dumps({**self.metadata(), "raw_output": value}))

    def test_worker_duration_must_be_finite_nonnegative_number(self):
        for value in (True, "1.25", None, -1, float("nan"), float("inf"), 10**400):
            with self.subTest(value=value):
                self.assert_invalid_worker(json.dumps({**self.metadata(), "inference_wall_time_s": value}))

    def test_duplicate_metadata_and_nonjson_output_are_rejected(self):
        duplicate = json.dumps(self.metadata())[:-1] + ',"device":"cpu"}'
        for stdout in (duplicate, "worker log\n" + json.dumps(self.metadata()), json.dumps(self.metadata()) + "{}"):
            with self.subTest(stdout=stdout):
                self.assert_invalid_worker(stdout)

    def test_semantic_refusal_remains_distinct_from_worker_error(self):
        metadata = {**self.metadata(), "raw_output": '{"status":"reject","reason":"No blue cube exists."}'}
        with self.assertRaisesRegex(RejectedInstruction, "No blue cube exists"):
            self.infer_from_stdout(json.dumps(metadata))


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
