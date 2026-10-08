"""Compare rules and the actual local model on a small, fixed language check."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from planning.language import parse_instruction
from planning.guarded_language import check_goal, check_request
from planning.llm import EXAMPLES, MODEL_ID, MODEL_REVISION, SYSTEM_PROMPT, LocalGoalModel, RejectedInstruction, parse_model_output
from planning.symbolic import Goal


def score_model_output(raw_output: str, expected_goal: dict | None) -> dict:
    try:
        goal = parse_model_output(raw_output).to_dict()
        return {"status": "accepted", "goal": goal, "correct": goal == expected_goal}
    except RejectedInstruction as error:
        return {"status": "rejected", "goal": None, "reason": str(error), "correct": expected_goal is None}
    except ValueError as error:
        return {"status": "invalid_output", "goal": None, "reason": str(error), "correct": False}


def score_guarded_output(instruction: str, raw_output: str, expected_goal: dict | None) -> dict:
    """Score the hybrid path separately; retain raw model results for comparison."""
    source = "guard"
    try:
        hints = check_request(instruction)
        try:
            goal = parse_instruction(instruction)
            source = "rules"
        except ValueError:
            source = "llm"
            goal = parse_model_output(raw_output)
        # An explicit model refusal stays attributed to the model.
        source_before_check = source
        source = "guard"
        goal = check_goal(hints, goal).to_dict()
        return {"status": "accepted", "source": source_before_check, "goal": goal, "correct": goal == expected_goal}
    except RejectedInstruction as error:
        return {"status": "rejected", "source": source, "goal": None,
                "reason": str(error), "correct": expected_goal is None}
    except ValueError as error:
        return {"status": "invalid_output", "source": source, "goal": None, "reason": str(error), "correct": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="New project-local directory for the complete language report.")
    parser.add_argument("--cases", type=Path, default=PROJECT / "evaluation/language_cases.json")
    parser.add_argument("--guarded", action="store_true", help="Also score literal checks plus rules/model; raw model runs on every case.")
    args = parser.parse_args()
    output = (args.output or PROJECT / ".cache/day6" / datetime.now(timezone.utc).strftime("language_%Y%m%dT%H%M%S%fZ")).resolve()
    if not output.is_relative_to(PROJECT) or output == PROJECT or output.exists():
        parser.error("--output must be a new directory inside the project")
    cases_path = args.cases.resolve()
    if not cases_path.is_relative_to(PROJECT) or not cases_path.is_file():
        parser.error("--cases must be an existing file inside the project")
    cases = json.loads(cases_path.read_text())
    for case in cases:
        if case["expected_goal"] is not None:
            Goal(**case["expected_goal"])
    output.mkdir(parents=True)
    model = LocalGoalModel()
    import transformers

    report = {
        "schema_version": 1, "started_at_utc": datetime.now(timezone.utc).isoformat(),
        "cases_path": str(cases_path.relative_to(PROJECT)), "guarded_enabled": args.guarded,
        "model": {"id": MODEL_ID, "revision": MODEL_REVISION, "device": "cpu", "dtype": "float32",
                  "max_new_tokens": 128, "do_sample": False, "cpu_threads": 8,
                  "transformers_version": transformers.__version__, "torch_version": model.torch.__version__},
        "prompt": {"system": SYSTEM_PROMPT, "examples": [{"instruction": request, "response": response} for request, response in EXAMPLES]},
        "trials": [],
    }
    for index, case in enumerate(cases, 1):
        expected = case["expected_goal"]
        try:
            rule_goal = parse_instruction(case["instruction"]).to_dict()
            rule_result = {"status": "accepted", "goal": rule_goal, "correct": rule_goal == expected}
        except ValueError:
            rule_result = {"status": "rejected", "goal": None, "correct": expected is None}
        start = time.monotonic()
        raw = model.generate(case["instruction"])
        llm_result = score_model_output(raw, expected)
        report["trials"].append({**case, "rules": rule_result, "llm": llm_result,
                                 "raw_model_output": raw, "generation_wall_time_s": time.monotonic() - start})
        if args.guarded:
            report["trials"][-1]["guarded"] = score_guarded_output(case["instruction"], raw, expected)
        rows = report["trials"]
        report["summary"] = {
            "planned": len(cases), "completed": len(rows), "complete": len(rows) == len(cases),
            "rules_correct": sum(row["rules"]["correct"] for row in rows),
            "llm_correct": sum(row["llm"]["correct"] for row in rows),
            "llm_false_acceptances": sum(row["expected_goal"] is None and row["llm"]["status"] == "accepted" for row in rows),
            "llm_invalid_outputs": sum(row["llm"]["status"] == "invalid_output" for row in rows),
        }
        if args.guarded:
            report["summary"].update({
                "guarded_correct": sum(row["guarded"]["correct"] for row in rows),
                "guarded_false_acceptances": sum(row["expected_goal"] is None and row["guarded"]["status"] == "accepted" for row in rows),
                "guarded_invalid_outputs": sum(row["guarded"]["status"] == "invalid_output" for row in rows),
            })
        temporary = output / "report.tmp"
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
        temporary.replace(output / "report.json")
        print(f"[CASE] {index}/{len(cases)} {case['id']}: rules={rule_result['correct']} llm={llm_result['correct']}", flush=True)
    print(f"[SUMMARY] {json.dumps(report['summary'])}", flush=True)
    print(f"[REPORT] {output / 'report.json'}", flush=True)
    return 0  # A language check keeps incorrect predictions as results, not process failures.


if __name__ == "__main__":
    raise SystemExit(main())
