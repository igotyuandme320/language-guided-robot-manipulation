"""Day 3: pick the red cube, optionally place it on the green platform.

Run from IsaacLab with uv run --no-sync python <this file> --viz kit --livestream 2.
Success is measured from the cube's observed pose, not from the skill phase.
"""

import argparse
import math
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Pick a red cube and optionally place it using Panda differential IK.")
parser.add_argument("--max_steps", type=int, help="Attempt timeout: default 3000 for pick, 6000 with --place.")
parser.add_argument("--place", action="store_true", help="After a verified lift, place the cube on the green platform.")
parser.add_argument("--cube_x", type=float, default=0.5, help="Initial cube x position in meters.")
parser.add_argument("--cube_y", type=float, default=0.0, help="Initial cube y position in meters.")
parser.add_argument("--screenshot", type=Path, help="Save the viewport after verified task success.")
parser.add_argument("--keep_open", action="store_true", help="Hold the final arm pose until the app is closed.")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
if args_cli.max_steps is None:
    args_cli.max_steps = 6000 if args_cli.place else 3000
if args_cli.max_steps <= 0:
    parser.error("--max_steps must be positive")
if not (math.isfinite(args_cli.cube_x) and math.isfinite(args_cli.cube_y)):
    parser.error("cube positions must be finite")
if not (0.35 <= args_cli.cube_x <= 0.65 and -0.15 <= args_cli.cube_y <= 0.15):
    parser.error("cube position must be inside the allowed tabletop region: x=[0.35,0.65], y=[-0.15,0.15]")

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

from execution.franka import execute_goal
from planning.symbolic import Goal


def main():
    goal = Goal("place", "red_cube", "green_platform") if args_cli.place else Goal("pick", "red_cube")
    execute_goal(goal, args_cli, simulation_app)


if __name__ == "__main__":
    exit_code = 0
    try:
        main()
    except KeyboardInterrupt:
        print("[INFO] Interrupted by user.", flush=True)
        exit_code = 130
    except Exception:
        traceback.print_exc()
        exit_code = 1
    finally:
        simulation_app.close(exit_code=exit_code)
