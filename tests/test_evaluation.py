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
FAILURE = {
    "goal": GOAL, "plan": RESULT["plan"], "reason": "lost_grasp",
    "last_verified_state": {"cube_location": "gripper"},
    "active_skill": "place", "phase": "TRANSIT", "attempted_steps": 1833,
    "max_steps": 6000, "physics_dt_s": 0.01,
    "observed_cube_position_m": [0.498, 0.00015, 0.0235],
    "cube_tcp_distance_m": 0.18, "grasp_loss_duration_s": 0.10,
}
PROJECT = Path(__file__).resolve().parents[1]
SCRIPT = PROJECT / "scripts/day5_evaluate.py"
CACHE = PROJECT / ".cache" / "evaluation_tests"


def result_output(result):
    return '[WORLD] {"cube_location": "table"}\n[RESULT] ' + json.dumps(result) + "\n"


class EvaluationTests(unittest.TestCase):
    def test_scene_observation_is_kept_with_the_execution_result(self):
        line = '[SCENE] {"configured_cube_yaw_deg": 30, "settled_cube_quaternion_xyzw": [0, 0, 0.258819, 0.965926]}'
        trial = summarize_output(line + "\n" + result_output(RESULT), 0, GOAL)
        self.assertEqual(trial["status"], "success")
        self.assertIn(line, trial["trace"])

    def test_structured_failure_preserves_cause_and_history(self):
        line = "[FAILURE] " + json.dumps(FAILURE)
        trial = summarize_output(line + "\nRuntimeError: placement failed", 1, GOAL)
        self.assertEqual(trial["status"], "failure")
        self.assertEqual(trial.get("failure"), FAILURE)
        self.assertIn("lost_grasp", trial["reason"])
        self.assertIn(line, trial["trace"])
        self.assertIsNone(trial["result"])

    def test_failure_record_prevents_success_despite_zero_exit(self):
        output = "[FAILURE] " + json.dumps(FAILURE) + "\n" + result_output(RESULT)
        trial = summarize_output(output, 0, GOAL)
        self.assertEqual(trial["status"], "failure")
        self.assertEqual(trial.get("failure"), FAILURE)
        self.assertIsNone(trial["result"])

    def test_invalid_failure_records_still_prevent_clean_success(self):
        for candidate in ([], {**FAILURE, "goal": {"action": "pick"}},
                          {**FAILURE, "reason": "invented"}, {**FAILURE, "attempted_steps": True},
                          {**FAILURE, "attempted_steps": 6001}, {**FAILURE, "cube_tcp_distance_m": float("nan")}):
            with self.subTest(candidate=candidate):
                line = "[FAILURE] " + json.dumps(candidate)
                trial = summarize_output(line + "\n" + result_output(RESULT), 0, GOAL)
                self.assertEqual(trial["status"], "failure")
                self.assertIsNone(trial.get("failure"))
                self.assertIn(line, trial["trace"])

    def test_malformed_failure_markers_prevent_success(self):
        for line in ("[FAILURE]", "[FAILURE]{invalid}", "[FAILURE]\t" + json.dumps(FAILURE)):
            with self.subTest(line=line):
                trial = summarize_output(line + "\n" + result_output(RESULT), 0, GOAL)
                self.assertEqual(trial["status"], "failure")
                self.assertIsNone(trial["result"])
                self.assertIn(line, trial["trace"])

    def test_timeout_preserves_reported_failure_but_stays_incomplete(self):
        trial = summarize_output("[FAILURE] " + json.dumps(FAILURE), None, GOAL)
        self.assertEqual(trial["status"], "timeout")
        self.assertEqual(trial.get("failure"), FAILURE)
        self.assertIsNone(trial["returncode"])

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

    def test_claimed_platform_state_requires_measured_platform_pose(self):
        for position in ((0.5, 0.0, 0.04), (0.5, -0.22, 0.10), (0.55, -0.22, 0.04)):
            with self.subTest(position=position):
                result = {**RESULT, "final_cube_position_m": list(position)}
                trial = summarize_output(result_output(result), 0, GOAL)
                self.assertEqual(trial["status"], "failure")
                self.assertIsNone(trial["result"])
                self.assertIn("platform placement tolerances", trial["reason"])

    def test_pose_inside_platform_tolerance_remains_valid(self):
        result = {**RESULT, "final_cube_position_m": [0.52, -0.20, 0.043]}
        self.assertEqual(summarize_output(result_output(result), 0, GOAL)["status"], "success")

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

    def test_seeded_preview_repeats_poses_and_pairs_languages(self):
        args = ("--dry_run", "--random_poses", "4", "--seed", "20")
        first = self.run_cli(*args)
        self.assertEqual(first.returncode, 0, first.stderr)
        protocol = json.loads(first.stdout)
        self.assertEqual(protocol, json.loads(self.run_cli(*args).stdout))
        other = self.run_cli("--dry_run", "--random_poses", "4", "--seed", "21")
        self.assertEqual(other.returncode, 0, other.stderr)
        cases = protocol["cases"]
        self.assertEqual(len(cases), 8)
        self.assertEqual(len({case["case_id"] for case in cases}), 8)
        self.assertNotEqual(cases, json.loads(other.stdout)["cases"])
        for index in range(0, 8, 2):
            pair = cases[index:index + 2]
            for field in ("cube_x", "cube_y", "cube_yaw_deg"):
                self.assertEqual(pair[0][field], pair[1][field])
            self.assertEqual({case["instruction"] for case in pair},
                             {"put the red cube on the green platform", "把红色方块放到绿色平台上"})
            self.assertTrue(0.4 <= pair[0]["cube_x"] <= 0.6)
            self.assertTrue(-0.1 <= pair[0]["cube_y"] <= 0.1)
            self.assertTrue(-45 <= pair[0]["cube_yaw_deg"] <= 45)

    def test_random_preview_limit_keeps_the_protocol_prefix(self):
        full = self.run_cli("--dry_run", "--random_poses", "2", "--seed", "20")
        limited = self.run_cli("--dry_run", "--random_poses", "2", "--seed", "20", "--limit", "3")
        self.assertEqual(full.returncode, 0, full.stderr)
        self.assertEqual(limited.returncode, 0, limited.stderr)
        self.assertEqual(json.loads(limited.stdout)["cases"], json.loads(full.stdout)["cases"][:3])
        self.assertEqual(len(json.loads(limited.stdout)["cases"]), 3)

    def test_invalid_sample_counts_and_limits_are_rejected(self):
        for args in (("--random_poses", "0"), ("--random_poses", "-1"),
                     ("--random_poses", "2", "--limit", "5"), ("--limit", "0"), ("--limit", "19")):
            with self.subTest(args=args):
                process = self.run_cli("--dry_run", *args)
                self.assertEqual(process.returncode, 2, process.stderr)
                self.assertNotIn("[TRIAL]", process.stdout)

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
