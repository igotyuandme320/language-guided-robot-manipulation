"""Language command -> goal -> verified skills; rules, model, or guarded model."""

import argparse
import json
import math
import os
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from isaaclab.app import AppLauncher

from planning.language import parse_instruction
from planning.symbolic import WorldState, plan_goal

parser = argparse.ArgumentParser(description="Execute a supported English/Chinese tabletop instruction.")
parser.add_argument("--instruction", required=True, help="A supported pick or place request.")
parser.add_argument("--language_backend", choices=("rules", "llm", "guarded"), default="rules")
parser.add_argument("--llm_timeout", type=float, default=120.0, help="CPU model worker deadline in seconds.")
parser.add_argument("--dry_run", action="store_true", help="Print goal/plan JSON for the selected initial scene; do not launch Kit.")
parser.add_argument("--max_steps", type=int, help="Attempt timeout: default 3000 for pick, 6000 for place.")
parser.add_argument("--cube_start", choices=("table", "green_platform"), default="table", help="Initial cube surface; live planning still uses settled observations.")
parser.add_argument("--cube_x", type=float, help="Table start x coordinate; default 0.5 m.")
parser.add_argument("--cube_y", type=float, help="Table start y coordinate; default 0 m.")
parser.add_argument("--cube_yaw_deg", type=float, default=0.0, help="Initial cube rotation about world z, in degrees [-180,180].")
parser.add_argument("--screenshot", type=Path, help="Save the viewport after verified task success.")
parser.add_argument("--record_gif", type=Path, help="New project-local GIF and JSON of real viewport frames after success.")
faults = parser.add_mutually_exclusive_group()
faults.add_argument("--gripper_stuck_open", action="store_true", help="Inject a simulated open-gripper fault to check failure detection.")
faults.add_argument("--release_after_pick", action="store_true", help="Inject open fingers during placement after a verified pick.")
parser.add_argument("--keep_open", action="store_true", help="Hold the final arm pose until the app is closed.")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
if args_cli.max_steps is not None and args_cli.max_steps <= 0:
    parser.error("--max_steps must be positive")
if not math.isfinite(args_cli.llm_timeout) or args_cli.llm_timeout <= 0:
    parser.error("--llm_timeout must be positive and finite")
if not math.isfinite(args_cli.cube_yaw_deg) or not -180 <= args_cli.cube_yaw_deg <= 180:
    parser.error("cube yaw must be finite and inside [-180,180] degrees")
if args_cli.cube_start == "green_platform" and (args_cli.cube_x is not None or args_cli.cube_y is not None):
    parser.error("--cube_x and --cube_y are table coordinates; omit them for a platform start")
args_cli.cube_x = 0.5 if args_cli.cube_x is None else args_cli.cube_x
args_cli.cube_y = 0.0 if args_cli.cube_y is None else args_cli.cube_y
if not (math.isfinite(args_cli.cube_x) and math.isfinite(args_cli.cube_y)):
    parser.error("cube positions must be finite")
if not (0.35 <= args_cli.cube_x <= 0.65 and -0.15 <= args_cli.cube_y <= 0.15):
    parser.error("cube position must be inside the allowed tabletop region: x=[0.35,0.65], y=[-0.15,0.15]")
if args_cli.record_gif:
    from execution.recording import validate_recording_path
    try:
        args_cli.record_gif = validate_recording_path(args_cli.record_gif)
    except ValueError as error:
        parser.error(str(error))
    streaming = args_cli.livestream if args_cli.livestream >= 0 else os.environ.get("LIVESTREAM", "0")
    if "kit" not in (args_cli.visualizer or []) and str(streaming) not in ("1", "2"):
        parser.error("recording requires --viz kit or --livestream 2")
language_metadata = None
try:
    if args_cli.language_backend == "llm":
        from planning.llm import infer_goal
        goal, language_metadata = infer_goal(args_cli.instruction, args_cli.llm_timeout)
    elif args_cli.language_backend == "guarded":
        from planning.guarded_language import infer_guarded
        goal, language_metadata = infer_guarded(args_cli.instruction, args_cli.llm_timeout)
    else:
        goal = parse_instruction(args_cli.instruction)
except ValueError as error:
    parser.error(str(error))
if args_cli.release_after_pick and (goal.action != "place" or args_cli.cube_start != "table"):
    parser.error("--release_after_pick requires a table-start placement with pick then place")
if args_cli.record_gif and args_cli.cube_start == "green_platform" and goal.action == "place":
    parser.error("The placement goal is already satisfied at this start; use --screenshot instead of motion recording")
if args_cli.max_steps is None:
    args_cli.max_steps = 6000 if goal.action == "place" else 3000
args_cli.language_metadata = language_metadata

if args_cli.dry_run:
    assumed_state = WorldState(args_cli.cube_start)
    preview = {
        "instruction": args_cli.instruction,
        "goal": goal.to_dict(),
        "assumed_state": assumed_state.to_dict(),
        "plan": [call.to_dict() for call in plan_goal(goal, assumed_state)],
    }
    if language_metadata is not None:
        preview["language_frontend" if args_cli.language_backend == "guarded" else "language_model"] = language_metadata
    if args_cli.gripper_stuck_open:
        preview["injected_fault"] = {"gripper_stuck_open": True}
    if args_cli.release_after_pick:
        preview["injected_fault"] = {"release_after_pick": True}
    if args_cli.cube_yaw_deg:
        preview["initial_cube_yaw_deg"] = args_cli.cube_yaw_deg
    print(json.dumps(preview, ensure_ascii=False, indent=2))
    raise SystemExit(0)

if language_metadata is not None:
    print(f"[LANGUAGE] {json.dumps(language_metadata, ensure_ascii=False)}", flush=True)
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
