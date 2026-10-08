"""Keep failed, incomplete, or malformed trials out of the success count."""

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from scripts.day5_evaluate import summarize_output, summarize_results


GOAL = {"action": "place", "object": "red_cube", "target": "green_platform"}
RESULT = {
    "goal": GOAL,
    "plan": [
        {"skill": "pick", "object": "red_cube", "target": None},
        {"skill": "place", "object": "red_cube", "target": "green_platform"},
    ],
    "final_state": {"cube_location": "green_platform"},
    "initial_cube_position_m": [0.5, 0.0, 0.017],
    "final_cube_position_m": [0.50018, -0.21948, 0.04],
    "steps": 2554,
    "physics_dt_s": 0.01,
    "cube_rise_m": 0.1985,
    "stable_hold_s": 0.5,
}
PROJECT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT / "scripts/day5_evaluate.py"
CACHE = PROJECT / ".cache" / "evaluation_tests"


def result_output(result):
    return '[WORLD] {"cube_location": "table"}\n[RESULT] ' + json.dumps(result) + "\n"


class EvaluationTests(unittest.TestCase):
    def test_complete_verified_result_is_collected(self):
        trial = summarize_output(result_output(RESULT), 0, GOAL)
        self.assertEqual(trial["status"], "success")
        self.assertEqual(trial["result"]["steps"], 2554)
        self.assertEqual(trial["result"]["final_cube_position_m"], [0.50018, -0.21948, 0.04])

    def test_clean_exit_without_verified_result_is_failure(self):
        trial = summarize_output('[WORLD] {"cube_location": "table"}\n', 0, GOAL)
        self.assertEqual(trial["status"], "failure")
        self.assertIsNone(trial["result"])

    def test_nonzero_exit_is_failure_even_after_result(self):
        trial = summarize_output(result_output(RESULT), 1, GOAL)
        self.assertEqual(trial["status"], "failure")

    def test_process_timeout_is_never_success(self):
        trial = summarize_output(result_output(RESULT), None, GOAL)
        self.assertEqual(trial["status"], "timeout")

    def test_wrong_goal_or_final_state_is_failure(self):
        for field, value in (("goal", {"action": "pick", "object": "red_cube", "target": None}),
                             ("final_state", {"cube_location": "gripper"})):
            with self.subTest(field=field):
                result = copy.deepcopy(RESULT)
                result[field] = value
                self.assertEqual(summarize_output(result_output(result), 0, GOAL)["status"], "failure")

    def test_malformed_or_nonfinite_metrics_are_failure(self):
        for output in ('[RESULT] {broken json}', result_output({}),
                       result_output({**RESULT, "cube_rise_m": float("nan")}),
                       result_output({**RESULT, "cube_rise_m": True, "stable_hold_s": True, "physics_dt_s": True}),
                       result_output({**RESULT, "cube_rise_m": 10 ** 400}),
                       result_output({**RESULT, "steps": -1}),
                       result_output({**RESULT, "initial_cube_position_m": [True, 0.0, 0.017]}),
                       result_output({**RESULT, "final_cube_position_m": [0.5, 0.0]})):
            with self.subTest(output=output):
                self.assertEqual(summarize_output(output, 0, GOAL)["status"], "failure")

    def test_failures_remain_in_the_denominator(self):
        summary = summarize_results([{"status": "success"}, {"status": "failure"}, {"status": "timeout"}], 3)
        self.assertEqual(summary["attempted"], 3)
        self.assertEqual(summary["verified_successes"], 1)
        self.assertEqual(summary["failures"], 2)
        self.assertAlmostEqual(summary["success_rate"], 1 / 3)
        self.assertTrue(summary["complete"])

    def test_partial_report_is_not_a_complete_experiment(self):
        summary = summarize_results([{"status": "success"}], 18)
        self.assertFalse(summary["complete"])
        self.assertEqual(summary["planned"], 18)
        self.assertIsNone(summarize_results([], 18)["success_rate"])


class EvaluationRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        CACHE.mkdir(parents=True, exist_ok=True)

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)

    def test_preview_covers_nine_positions_in_both_languages(self):
        process = self.run_cli("--dry_run")
        self.assertEqual(process.returncode, 0, process.stderr)
        cases = json.loads(process.stdout)["cases"]
        self.assertEqual(len(cases), 18)
        positions = {(case["cube_x"], case["cube_y"]) for case in cases}
        self.assertEqual(positions, {(x, y) for x in (0.4, 0.5, 0.6) for y in (-0.1, 0.0, 0.1)})
        for x, y in positions:
            instructions = {case["instruction"] for case in cases if (case["cube_x"], case["cube_y"]) == (x, y)}
            self.assertEqual(instructions, {"put the red cube on the green platform", "把红色方块放到绿色平台上"})

    def test_preview_can_limit_a_smoke_run(self):
        process = self.run_cli("--dry_run", "--limit", "1")
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(len(json.loads(process.stdout)["cases"]), 1)

    def test_invalid_timeouts_are_rejected_before_running(self):
        for args in (("--max_steps", "0"), ("--process_timeout", "nan"), ("--process_timeout", "-1")):
            with self.subTest(args=args):
                process = self.run_cli(*args)
                self.assertEqual(process.returncode, 2, process.stderr)
                self.assertNotIn("[TRIAL]", process.stdout)

    def test_existing_output_is_protected(self):
        with tempfile.TemporaryDirectory(dir=CACHE) as directory:
            sentinel = Path(directory) / "report.json"
            sentinel.write_text("previous experiment")
            process = self.run_cli("--output", directory)
            self.assertEqual(process.returncode, 2, process.stderr)
            self.assertEqual(sentinel.read_text(), "previous experiment")

    def test_output_outside_project_is_rejected(self):
        process = self.run_cli("--output", str(PROJECT.parent / "outside_project"))
        self.assertEqual(process.returncode, 2, process.stderr)
        self.assertNotIn("[TRIAL]", process.stdout)

    def test_real_process_deadline_preserves_partial_log(self):
        from scripts.day5_evaluate import run_trial
        with tempfile.TemporaryDirectory(dir=CACHE) as directory:
            log = Path(directory) / "timeout.log"
            start = time.monotonic()
            returncode, elapsed = run_trial(
                [sys.executable, "-c", "import time; print('child started', flush=True); time.sleep(60)"],
                log, 0.2,
            )
            self.assertIsNone(returncode)
            self.assertIn("child started", log.read_text())
            self.assertGreaterEqual(elapsed, 0.2)
            self.assertLess(time.monotonic() - start, 3)


if __name__ == "__main__":
    unittest.main()
