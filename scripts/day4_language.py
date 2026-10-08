"""Day 4: a rule-based language command -> goal -> plan -> verified Franka skills."""

import argparse
import json
import math
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from isaaclab.app import AppLauncher

from planning.language import parse_instruction
from planning.symbolic import WorldState, plan_goal

parser = argparse.ArgumentParser(description="Execute a supported English/Chinese tabletop instruction.")
parser.add_argument("--instruction", required=True, help="A supported pick or place request.")
parser.add_argument("--dry_run", action="store_true", help="Print goal/plan JSON for a fresh table scene; do not launch Kit.")
parser.add_argument("--max_steps", type=int, help="Attempt timeout: default 3000 for pick, 6000 for place.")
parser.add_argument("--cube_x", type=float, default=0.5)
parser.add_argument("--cube_y", type=float, default=0.0)
parser.add_argument("--screenshot", type=Path, help="Save the viewport after verified task success.")
parser.add_argument("--keep_open", action="store_true", help="Hold the final arm pose until the app is closed.")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
try:
    goal = parse_instruction(args_cli.instruction)
except ValueError as error:
    parser.error(str(error))
if args_cli.max_steps is None:
    args_cli.max_steps = 6000 if goal.action == "place" else 3000
if args_cli.max_steps <= 0:
    parser.error("--max_steps must be positive")
if not (math.isfinite(args_cli.cube_x) and math.isfinite(args_cli.cube_y)):
    parser.error("cube positions must be finite")
if not (0.35 <= args_cli.cube_x <= 0.65 and -0.15 <= args_cli.cube_y <= 0.15):
    parser.error("cube position must be inside the allowed tabletop region: x=[0.35,0.65], y=[-0.15,0.15]")

if args_cli.dry_run:
    assumed_state = WorldState("table")
    print(json.dumps({
        "instruction": args_cli.instruction,
        "goal": goal.to_dict(),
        "assumed_state": assumed_state.to_dict(),
        "plan": [call.to_dict() for call in plan_goal(goal, assumed_state)],
    }, ensure_ascii=False, indent=2))
    raise SystemExit(0)

print(f"[GOAL] {json.dumps(goal.to_dict())}", flush=True)
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

from execution.franka import execute_goal

if __name__ == "__main__":
    exit_code = 0
    try:
        execute_goal(goal, args_cli, simulation_app)
    except KeyboardInterrupt:
        print("[INFO] Interrupted by user.", flush=True)
        exit_code = 130
    except Exception:
        traceback.print_exc()
        exit_code = 1
    finally:
        simulation_app.close(exit_code=exit_code)
