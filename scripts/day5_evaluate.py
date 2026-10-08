"""Evaluate the existing Day 4 demo on a fixed grid, with no controller tuning."""

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from planning.symbolic import Goal, WorldState, plan_goal

PROJECT = Path(__file__).resolve().parents[1]
# This fixed-grid protocol uses the default scene's platform destination.
# These checks also match the executor's final placement tolerances.
EXPECTED_PLATFORM_CUBE_CENTER = (0.5, -0.22, 0.04)
PLACEMENT_XY_TOLERANCE = 0.04
PLACEMENT_Z_TOLERANCE = 0.008
INSTRUCTIONS = (
    ("en", "put the red cube on the green platform"),
    ("zh", "把红色方块放到绿色平台上"),
)


def parse_failure_record(text: str, expected_goal: dict) -> dict:
    """Check diagnostic metadata; this does not re-observe a physical failure."""
    candidate = json.loads(text)
    if not isinstance(candidate, dict) or candidate.get("goal") != expected_goal:
        raise ValueError("Unexpected failure goal.")
    expected_plan = [call.to_dict() for call in plan_goal(Goal(**expected_goal), WorldState("table"))]
    if candidate.get("plan") != expected_plan:
        raise ValueError("Unexpected failure plan.")
    if candidate.get("reason") not in ("step_limit", "app_closed", "lost_grasp"):
        raise ValueError("Unknown execution failure reason.")
    if candidate.get("active_skill") not in ("pick", "place") or not isinstance(candidate.get("phase"), str) or not candidate["phase"]:
        raise ValueError("Invalid failure stage.")
    WorldState(**candidate["last_verified_state"])
    attempted, maximum = candidate["attempted_steps"], candidate["max_steps"]
    if type(attempted) is not int or type(maximum) is not int or maximum <= 0 or not 0 <= attempted <= maximum:
        raise ValueError("Invalid failure step counts.")
    dt = candidate["physics_dt_s"]
    if type(dt) not in (int, float) or not math.isfinite(dt) or dt <= 0:
        raise ValueError("Invalid failure physics timestep.")
    position = candidate["observed_cube_position_m"]
    if len(position) != 3 or not all(type(value) in (int, float) and math.isfinite(value) for value in position):
        raise ValueError("Invalid failure cube coordinates.")
    # Extensions are retained, but cannot make the saved report non-JSON.
    json.dumps(candidate, allow_nan=False)
    return candidate


def summarize_output(output: str, returncode: int | None, expected_goal: dict) -> dict:
    """An exit code alone is not proof of a completed manipulation attempt."""
    lines = output.splitlines()
    trace = [line for line in lines if line.startswith((
        "[GOAL]", "[PLAN]", "[WORLD]", "[CHECK]", "[RESULT]", "[FAILURE]", "[SUCCESS]", "[PHASE]", "[STATE]",
        "RuntimeError:", "ValueError:",
    ))]
    result = None
    failure = None
    failure_lines = [line.removeprefix("[FAILURE]").lstrip() for line in lines if line.startswith("[FAILURE]")]
    if len(failure_lines) == 1:
        try:
            failure = parse_failure_record(failure_lines[0], expected_goal)
        except (KeyError, TypeError, ValueError, OverflowError):
            pass  # Preserve the raw trace, but do not label malformed metadata as checked.
    reason = "Missing or invalid verified result."
    result_lines = [line.removeprefix("[RESULT] ") for line in lines if line.startswith("[RESULT] ")]
    if len(result_lines) == 1:
        try:
            candidate = json.loads(result_lines[0])
            goal = Goal(**candidate["goal"])
            if candidate["goal"] != expected_goal or candidate["final_state"] != {"cube_location": "green_platform"}:
                raise ValueError("Unexpected goal or final state.")
            if candidate["plan"] != [call.to_dict() for call in plan_goal(goal, WorldState("table"))]:
                raise ValueError("Unexpected plan.")
            for field in ("initial_cube_position_m", "final_cube_position_m"):
                position = candidate[field]
                if len(position) != 3 or not all(type(value) in (int, float) and math.isfinite(value) for value in position):
                    raise ValueError("Invalid cube coordinates.")
            final_cube = candidate["final_cube_position_m"]
            if (math.dist(final_cube[:2], EXPECTED_PLATFORM_CUBE_CENTER[:2]) >= PLACEMENT_XY_TOLERANCE
                    or abs(final_cube[2] - EXPECTED_PLATFORM_CUBE_CENTER[2]) >= PLACEMENT_Z_TOLERANCE):
                raise ValueError("Final cube pose is outside the platform placement tolerances.")
            for field in ("physics_dt_s", "cube_rise_m", "stable_hold_s"):
                if type(candidate[field]) not in (int, float) or not math.isfinite(candidate[field]) or candidate[field] <= 0:
                    raise ValueError("Invalid execution metrics.")
            if type(candidate["steps"]) is not int or candidate["steps"] <= 0:
                raise ValueError("Invalid step count.")
            if candidate["cube_rise_m"] < 0.10 or candidate["stable_hold_s"] < 0.5:
                raise ValueError("Physical verification thresholds were not met.")
            result = candidate
            reason = "Verified goal and clean process exit."
        except (KeyError, TypeError, ValueError, OverflowError) as error:
            reason = f"Invalid verified result: {error}"
    if returncode is None:
        status, reason = "timeout", "Simulation process exceeded the wall-clock timeout."
    elif returncode != 0:
        status = "failure"
        errors = [line for line in trace if line.startswith(("RuntimeError:", "ValueError:"))]
        if failure is not None:
            reason = f"Simulation reported {failure['reason']} during {failure['active_skill']} ({failure['phase']})."
        else:
            reason = errors[-1] if errors else f"Simulation process exited with code {returncode}."
    elif failure_lines:
        status, result = "failure", None
        reason = "A reported failure prevents a clean completion claim, despite exit code zero."
    else:
        status = "success" if result is not None else "failure"
    trial = {"status": status, "returncode": returncode, "reason": reason, "result": result, "trace": trace}
    if failure_lines:
        trial["failure"] = failure
    return trial


def summarize_results(trials: list[dict], planned_count: int) -> dict:
    successes = sum(trial["status"] == "success" for trial in trials)
    return {
        "planned": planned_count,
        "attempted": len(trials),
        "verified_successes": successes,
        "failures": len(trials) - successes,
        "timeouts": sum(trial["status"] == "timeout" for trial in trials),
        "success_rate": successes / len(trials) if trials else None,
        "complete": len(trials) == planned_count,
    }


def run_trial(command: list[str], log_path: Path, timeout: float) -> tuple[int | None, float]:
    """Keep the full child output on disk; subprocess.run kills a timed-out child."""
    start = time.monotonic()
    with log_path.open("w") as output:
        try:
            process = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT, timeout=timeout)
            returncode = process.returncode
        except subprocess.TimeoutExpired:
            returncode = None
    return returncode, time.monotonic() - start


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="New directory inside this repository for report and raw logs.")
    parser.add_argument("--dry_run", action="store_true", help="Preview the preset cases without launching Kit.")
    parser.add_argument("--limit", type=int, default=18, help="Run the first N cases, for a smoke check (1–18).")
    parser.add_argument("--max_steps", type=int, default=6000, help="Physics-step timeout for every placement attempt.")
    parser.add_argument("--process_timeout", type=float, default=120.0, help="Wall-clock timeout per fresh process, seconds.")
    args = parser.parse_args()
    if args.max_steps <= 0 or not 1 <= args.limit <= 18:
        parser.error("--max_steps must be positive and --limit must be between 1 and 18")
    if not math.isfinite(args.process_timeout) or args.process_timeout <= 0:
        parser.error("--process_timeout must be positive and finite")
    cases = [
        {"case_id": f"pose{index:02d}_{language}", "cube_x": x, "cube_y": y, "instruction": instruction}
        for index, (x, y) in enumerate(((x, y) for x in (0.4, 0.5, 0.6) for y in (-0.1, 0.0, 0.1)), 1)
        for language, instruction in INSTRUCTIONS
    ][:args.limit]
    protocol = {"cases": cases, "max_steps": args.max_steps, "process_timeout_s": args.process_timeout,
                "rendering": "disabled", "expected_platform_cube_center_m": EXPECTED_PLATFORM_CUBE_CENTER,
                "placement_xy_tolerance_m": PLACEMENT_XY_TOLERANCE, "placement_z_tolerance_m": PLACEMENT_Z_TOLERANCE}
    if args.dry_run:
        print(json.dumps(protocol, ensure_ascii=False, indent=2))
        return 0
    output = (args.output or PROJECT / ".cache/day5" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")).resolve()
    if not output.is_relative_to(PROJECT) or output == PROJECT:
        parser.error("--output must be a new directory inside the project repository")
    if output.exists():
        parser.error("--output already exists; choose a new directory to preserve previous results")
    output.mkdir(parents=True)
    report = {"schema_version": 1, "protocol": protocol, "started_at_utc": datetime.now(timezone.utc).isoformat(),
              "python_version": sys.version.split()[0], "interrupted": False, "trials": []}
    goal = Goal("place", "red_cube", "green_platform").to_dict()

    def save_report():
        report["summary"] = summarize_results(report["trials"], len(cases))
        temporary = output / "report.tmp"
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
        temporary.replace(output / "report.json")

    save_report()
    for index, case in enumerate(cases, 1):
        log_path = output / (case["case_id"] + ".log")
        command = [sys.executable, str(PROJECT / "scripts/day4_language.py"),
                   "--instruction", case["instruction"], "--cube_x", str(case["cube_x"]),
                   "--cube_y", str(case["cube_y"]), "--max_steps", str(args.max_steps)]
        print(f"[TRIAL] {index}/{len(cases)} {case['case_id']} x={case['cube_x']} y={case['cube_y']}", flush=True)
        start = time.monotonic()
        try:
            returncode, elapsed = run_trial(command, log_path, args.process_timeout)
        except KeyboardInterrupt:
            trial = summarize_output(log_path.read_text(), None, goal)
            trial.update(case, status="interrupted", reason="Batch interrupted by user; active child stopped.",
                         wall_time_s=time.monotonic() - start)
            report["trials"].append(trial)
            report["interrupted"] = True
            save_report()
            print(f"[INFO] Interrupted; partial report saved to {output / 'report.json'}", flush=True)
            return 130
        trial = summarize_output(log_path.read_text(), returncode, goal)
        trial.update(case, wall_time_s=elapsed)
        report["trials"].append(trial)
        save_report()
        print(f"[TRIAL] {case['case_id']}: {trial['status']} ({elapsed:.2f}s) — {trial['reason']}", flush=True)
    print(f"[SUMMARY] {json.dumps(report['summary'])}", flush=True)
    print(f"[REPORT] {output / 'report.json'}", flush=True)
    return 0 if report["summary"]["failures"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
