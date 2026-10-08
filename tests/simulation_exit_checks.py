"""Opt-in real-simulator checks; excluded from fast unittest discovery.

Run from IsaacLab with the same LD_LIBRARY_PATH as the demos:
    uv run --no-sync python ../language-guided-robot-manipulation/tests/simulation_exit_checks.py
"""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

PROJECT = Path(__file__).resolve().parents[1]
DEMO = PROJECT / "scripts/day3_pick.py"
LANGUAGE_DEMO = PROJECT / "scripts/day4_language.py"
EVALUATION = PROJECT / "scripts/day5_evaluate.py"
PLACE_INSTRUCTION = ["--instruction", "把红色方块放到绿色平台上"]


class SimulationExitTests(unittest.TestCase):
    def test_evaluation_step_timeouts_preserve_both_failed_trials(self):
        cache = PROJECT / ".cache" / "simulation_checks"
        cache.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as directory:
            output = Path(directory) / "experiment"
            result = subprocess.run(
                [sys.executable, str(EVALUATION), "--output", str(output), "--limit", "2", "--max_steps", "1"],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=60,
            )
            self.assertEqual(result.returncode, 1, result.stdout)
            report = json.loads((output / "report.json").read_text())
            self.assertEqual(report["summary"]["attempted"], 2)
            self.assertEqual(report["summary"]["failures"], 2)
            self.assertEqual(report["summary"]["verified_successes"], 0)
            self.assertTrue(report["summary"]["complete"])
            self.assertTrue(all(trial["result"] is None for trial in report["trials"]))

    def test_evaluation_interruption_preserves_partial_report(self):
        cache = PROJECT / ".cache" / "simulation_checks"
        cache.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as directory:
            output = Path(directory) / "experiment"
            console = Path(directory) / "console.log"
            with console.open("w") as stream:
                process = subprocess.Popen(
                    [sys.executable, str(EVALUATION), "--output", str(output)],
                    stdout=stream, stderr=subprocess.STDOUT, start_new_session=True,
                )
                try:
                    deadline = time.monotonic() + 30
                    child_log = output / "pose01_en.log"
                    started = False
                    while time.monotonic() < deadline and process.poll() is None:
                        if child_log.exists() and "[INFO] Starting cube position:" in child_log.read_text():
                            started = True
                            break
                        time.sleep(0.05)
                    self.assertTrue(started, console.read_text())
                    os.killpg(process.pid, signal.SIGINT)
                    self.assertEqual(process.wait(timeout=15), 130, console.read_text())
                    report = json.loads((output / "report.json").read_text())
                    self.assertTrue(report["interrupted"])
                    self.assertFalse(report["summary"]["complete"])
                    self.assertEqual(report["summary"]["attempted"], 1)
                    self.assertEqual(report["summary"]["verified_successes"], 0)
                    self.assertEqual(report["trials"][0]["status"], "interrupted")
                    # The parent catches Ctrl+C, so the child's actual exit code is unknown.
                    self.assertIsNone(report["trials"][0]["returncode"])
                finally:
                    if process.poll() is None:
                        os.killpg(process.pid, signal.SIGTERM)
                        process.wait(timeout=10)

    def test_short_attempt_exits_with_failure(self):
        result = subprocess.run(
            [sys.executable, str(DEMO), "--max_steps", "1"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=45,
        )
        self.assertEqual(result.returncode, 1, result.stdout[-3000:])
        self.assertIn("Pick failed", result.stdout)
        self.assertNotIn("[SUCCESS]", result.stdout)

    def test_interrupted_attempt_exits_130(self):
        self.check_interruption(DEMO, [])

    def test_language_interrupted_attempt_exits_130(self):
        self.check_interruption(LANGUAGE_DEMO, PLACE_INSTRUCTION)

    def test_language_timeout_does_not_commit_symbolic_effects(self):
        result = subprocess.run(
            [sys.executable, str(LANGUAGE_DEMO), *PLACE_INSTRUCTION, "--max_steps", "1"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=45,
        )
        self.assertEqual(result.returncode, 1, result.stdout[-3000:])
        worlds = [line for line in result.stdout.splitlines() if line.startswith("[WORLD]")]
        self.assertEqual(worlds, ['[WORLD] {"cube_location": "table"}'])
        self.assertNotIn("[SUCCESS]", result.stdout)

    def check_interruption(self, script, extra_args):
        # Keep scratch output inside our own repository.
        cache = PROJECT / ".cache" / "simulation_checks"
        cache.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", dir=cache) as output:
            # A separate reader avoids moving the child stdout file descriptor's offset.
            log_path = Path(output.name)
            process = subprocess.Popen(
                [sys.executable, str(script), *extra_args, "--max_steps", "3000"],
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                deadline = time.monotonic() + 30
                started = False
                while time.monotonic() < deadline and process.poll() is None:
                    if "[INFO] Starting cube position:" in log_path.read_text():
                        started = True
                        break
                    time.sleep(0.05)
                self.assertTrue(started, "Scene did not become ready before interrupt check")
                os.killpg(process.pid, signal.SIGINT)
                code = process.wait(timeout=15)
                self.assertEqual(code, 130, log_path.read_text()[-3000:])
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=10)


if __name__ == "__main__":
    unittest.main(verbosity=2)
