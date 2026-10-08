# Day 19 — Keeping failure details in evaluation reports

## Goal

The executor now reports a lost grasp before placement finishes. The
batch reader still mainly used the exit code and final exception text,
and omitted `[FAILURE]` from its saved trace. I wanted an evaluation row
to retain the actual reported reason and historical state.

## Change

The reader retains a single failure record after checking its matching
goal and fixed-table plan, recognized reason, skill/stage metadata,
valid symbolic state, step bounds, timestep, and observed cube coordinates.
Additional diagnostic fields are preserved if they can be saved as JSON.

A nonzero exit with a checked record gets a reason such as
`Simulation reported lost_grasp during place (TRANSIT).` Startup errors
without a structured record keep the earlier exception/exit-code path.
The raw failure line stays in the trace even when its metadata is invalid
or multiple records prevent an unambiguous single record.

For this single-attempt protocol, any failure line prevents a success
count even if the process returns zero and also prints an otherwise valid
result. A process timeout still counts as a timeout, with unknown exit
code, while preserving any failure already reported. Normal successful
row fields remain unchanged.

This is diagnostic validation, not a new physical observer. A retained
`last_verified_state` is still historical. The reader does not infer that
the cube is currently held or decide a recovery action from that field.
The protocol has no retries; a future multi-attempt protocol would need
explicit attempt boundaries rather than treating mixed records as success.

## Verification

Five new tests first failed on missing diagnostics or contradictory logs
being counted as successful. They now cover record preservation, a
failure/result pair with zero exit, malformed records, and timeout
precedence. Review found that a missing space after the failure marker
could bypass the first check; a regression test now covers bare, malformed,
and tab-separated markers. The malformed examples include wrong goals/reasons, invalid
step counts, and a non-JSON numeric value. These are synthetic reader
inputs, not robot failures observed in a new trial.

All 115 fast tests passed. The pure-Python CI subset has 85 tests.

I also rechecked existing recorded data:

| Saved inputs | Reader outcome |
| --- | --- |
| Day 5 placement traces | All 18 remain successful; result fields unchanged |
| Day 18 normal placement controls | All three remain successful; result fields unchanged |
| Day 18 post-pick release trace | Failure; reported `lost_grasp` retained |
| Day 9 open-gripper placement record | Failure; reported `step_limit` retained |

The [offline report](results/day19_failure_recheck.json) includes the
source-file hashes and all 23 rechecked rows. Day 9 reconstructs a log line
from the saved failure object; the other inputs use saved traces. The
historical measurements are unchanged. There was no new simulation or
model inference today, so these are not 23 new physical attempts or a
new success-rate experiment.

## Run the reader tests

From the existing `robot-demo` environment and Isaac Lab directory:

```bash
PYTHONPATH=../language-guided-robot-manipulation \
uv run --no-sync python -m unittest discover \
  -s ../language-guided-robot-manipulation/tests \
  -p test_evaluation.py -v
```

The existing Day 5 evaluation entry uses the revised reader automatically.
Its normal protocol does not inject a release fault.

## What I learned

An exit code describes the process, while a reported failure describes
what the executor observed. Keeping both makes a failed trial easier to
understand. Neither should be replaced by an optimistic success label,
and replaying a report is different from rerunning the robot.
