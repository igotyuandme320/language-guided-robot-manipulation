"""Opt-in real-simulator checks; excluded from fast unittest discovery.

Run from IsaacLab with the same LD_LIBRARY_PATH as the demos:
    uv run --no-sync python ../language-guided-robot-manipulation/tests/simulation_exit_checks.py
"""
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


class SimulationExitTests(unittest.TestCase):
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
        # Keep scratch output inside our own repository.
        cache = PROJECT / ".cache" / "simulation_checks"
        cache.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(mode="w+", dir=cache) as output:
            process = subprocess.Popen(
                [sys.executable, str(DEMO), "--max_steps", "3000"],
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            try:
                deadline = time.monotonic() + 30
                started = False
                while time.monotonic() < deadline and process.poll() is None:
                    output.seek(0)
                    if "[INFO] Starting cube position:" in output.read():
                        started = True
                        break
                    time.sleep(0.05)
                self.assertTrue(started, "Scene did not become ready before interrupt check")
                os.killpg(process.pid, signal.SIGINT)
                code = process.wait(timeout=15)
                output.seek(0)
                self.assertEqual(code, 130, output.read()[-3000:])
            finally:
                if process.poll() is None:
                    os.killpg(process.pid, signal.SIGTERM)
                    process.wait(timeout=10)


if __name__ == "__main__":
    unittest.main(verbosity=2)
