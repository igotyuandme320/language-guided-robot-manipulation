"""Preview and rejected requests must exit before launching a simulator."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/day4_language.py"


class LanguageCliTests(unittest.TestCase):
    def test_unsupported_followups_exit_before_model_and_app(self):
        for instruction, message in (("Pick up the red cube and hand it to me.", "Handover"),
                                     ("Place the red cube on the green platform and keep holding it.", "place skill releases"),
                                     ("Place the red cube on the green platform after the door opens.", "Conditional execution")):
            with self.subTest(instruction=instruction):
                result = self.run_cli(instruction, "--language_backend", "guarded", "--llm_timeout", "0.01")
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn(message, result.stderr)
                self.assertNotIn("timed out", result.stderr)
                self.assertNotIn("[ext:", result.stdout)

    def test_fault_is_visible_in_preview_without_changing_the_goal(self):
        result = self.run_cli("pick up the red cube", "--gripper_stuck_open", "--dry_run")
        self.assertEqual(result.returncode, 0, result.stderr)
        preview = json.loads(result.stdout)
        self.assertEqual(preview["goal"]["action"], "pick")
        self.assertEqual(preview["injected_fault"], {"gripper_stuck_open": True})

    def test_recording_requires_renderer_before_model_inference(self):
        result = self.run_cli("Please hold the red cube.", "--language_backend", "llm", "--llm_timeout", "0.01",
                              "--record_gif", str(SCRIPT.parents[1] / ".cache/day8/preview.gif"))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("recording requires", result.stderr)
        self.assertNotIn("timed out", result.stderr)
        self.assertNotIn("[ext:", result.stdout)

    def test_recording_refuses_existing_files_before_app_start(self):
        with tempfile.TemporaryDirectory(dir=SCRIPT.parents[1]) as directory:
            gif = Path(directory) / "keep.gif"
            gif.write_bytes(b"keep existing result")
            result = self.run_cli("pick up the red cube", "--record_gif", str(gif), "--viz", "kit")
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn("must not exist", result.stderr)
            self.assertEqual(gif.read_bytes(), b"keep existing result")
            self.assertNotIn("[ext:", result.stdout)

    def test_guarded_negation_is_blocked_before_model_or_app(self):
        result = self.run_cli("Do not lift the red cube.", "--language_backend", "guarded", "--llm_timeout", "0.01")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("Negated", result.stderr)
        self.assertNotIn("timed out", result.stderr)
        self.assertNotIn("[ext:", result.stdout)

    def test_guarded_template_preview_records_rule_source(self):
        result = self.run_cli("pick up the red cube", "--language_backend", "guarded", "--llm_timeout", "0.01", "--dry_run")
        self.assertEqual(result.returncode, 0, result.stderr)
        preview = json.loads(result.stdout)
        self.assertEqual(preview["language_frontend"], {"backend": "guarded", "source": "rules"})
        self.assertEqual(preview["goal"]["action"], "pick")

    def run_cli(self, instruction, *extra):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--instruction", instruction, *extra],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15,
        )

    def test_place_preview_is_json_with_ordered_skills(self):
        result = self.run_cli("put the red cube on the green platform", "--dry_run")
        self.assertEqual(result.returncode, 0, result.stderr)
        preview = json.loads(result.stdout)
        self.assertEqual(preview["goal"], {"action": "place", "object": "red_cube", "target": "green_platform"})
        self.assertEqual(preview["assumed_state"], {"cube_location": "table"})
        self.assertEqual([call["skill"] for call in preview["plan"]], ["pick", "place"])

    def test_chinese_pick_preview_has_one_skill(self):
        result = self.run_cli("请拿起红色方块。", "--dry_run")
        self.assertEqual(result.returncode, 0, result.stderr)
        preview = json.loads(result.stdout)
        self.assertEqual(preview["goal"], {"action": "pick", "object": "red_cube", "target": None})
        self.assertEqual([call["skill"] for call in preview["plan"]], ["pick"])

    def test_unsupported_live_request_is_rejected_before_app_start(self):
        result = self.run_cli("do not pick up the red cube")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("Unsupported instruction", result.stderr)
        self.assertNotIn("[ext:", result.stdout)
        self.assertNotIn("AppLauncher is deprecated", result.stderr)

    def test_invalid_timeout_is_rejected_even_in_preview(self):
        result = self.run_cli("pick up the red cube", "--max_steps", "0", "--dry_run")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("--max_steps must be positive", result.stderr)

    def test_llm_deadline_exits_before_simulator_start(self):
        result = self.run_cli("Could you move the red cube onto the green platform?",
                              "--language_backend", "llm", "--llm_timeout", "0.01", "--dry_run")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("inference timed out", result.stderr)
        self.assertNotIn("[ext:", result.stdout)
        self.assertNotIn("AppLauncher is deprecated", result.stderr)

    def test_invalid_llm_deadline_is_rejected(self):
        result = self.run_cli("pick up the red cube", "--llm_timeout", "nan", "--dry_run")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("positive and finite", result.stderr)


if __name__ == "__main__":
    unittest.main()
