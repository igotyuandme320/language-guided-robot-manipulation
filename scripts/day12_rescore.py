"""Replay saved Day 11 responses with current checks; no model or robot runs."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from scripts.day6_evaluate import score_guarded_output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="A new project-local report directory.")
    args = parser.parse_args()
    output = (args.output or PROJECT / ".cache/day12" / datetime.now(timezone.utc).strftime("replay_%Y%m%dT%H%M%S%fZ")).resolve()
    if not output.is_relative_to(PROJECT) or output == PROJECT or output.exists():
        parser.error("--output must be a new directory inside the project")
    source = PROJECT / "docs/results/day11_constraints.json"
    baseline = json.loads(source.read_text())
    rows = []
    for row in baseline["trials"]:
        rows.append({**row, "guarded_before": row["guarded"],
                     "guarded": score_guarded_output(row["instruction"], row["raw_model_output"], row["expected_goal"])})
    report = {
        "source_report": str(source.relative_to(PROJECT)), "inference_rerun": False,
        "note": "Only request checks rescored; the raw model responses and labels are unchanged. No robot execution.",
        "model": baseline["model"], "prompt": baseline["prompt"], "trials": rows,
        "summary": {
            "completed": len(rows), "baseline_guarded_correct": sum(r["guarded_before"]["correct"] for r in rows),
            "guarded_correct": sum(r["guarded"]["correct"] for r in rows),
            "baseline_false_acceptances": sum(r["expected_goal"] is None and r["guarded_before"]["status"] == "accepted" for r in rows),
            "guarded_false_acceptances": sum(r["expected_goal"] is None and r["guarded"]["status"] == "accepted" for r in rows),
        },
    }
    output.mkdir(parents=True)
    (output / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    print(json.dumps(report["summary"]))
    print(f"[REPORT] {output / 'report.json'}")


if __name__ == "__main__":
    main()
