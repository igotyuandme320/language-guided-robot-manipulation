"""Preview and rejected requests must exit before launching a simulator."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/day4_language.py"


class LanguageCliTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
