# Day 16 — Checking the measured pose in the batch report

## Goal

The executor already checks the cube's actual pose before recording a
placement effect. The Day 5 batch reader, however, only checked that the
result said `green_platform`, that coordinates were finite, and that
execution metrics met their thresholds. A synthetic result with the
right state string but a misplaced cube could enter the success count.

I wanted the report reader to catch that inconsistency too. This was a
gap in result validation, not an observed failed placement being hidden
in the Day 5 experiment.

## Change

The fixed-grid evaluator now checks final cube coordinates against the
default platform's expected cube center `(0.5, -0.22, 0.04)` m. It requires
horizontal error below 0.04 m and height error below 0.008 m, matching the
executor's placement tolerances. Invalid result records retain a validation
reason in the batch row. The expected destination and tolerances also
appear in new protocol previews and reports.

These constants belong to this fixed default-scene protocol. If I change
the platform geometry or pose, I need to update the protocol expectation.
The checker is not a general scene interpreter. The executor, robot
motion, success thresholds, and old measured results are unchanged.

## Verification

Before the fix, three synthetic misplaced records were incorrectly
accepted: wrong platform y position, an airborne cube, and a cube offset
by 5 cm in x. The new test rejects all three despite the claimed platform
state. A separate in-tolerance pose remains accepted. These are unit-test
fixtures, not robot trials.

All 101 fast tests passed. The pure-Python CI subset now has 75 tests.
I also passed all 18 saved Day 5 result traces through the revised reader:
all remain accepted, and their result fields are unchanged. Maximum
horizontal error is still about 3.19 mm, well within the 40 mm threshold.
The [recheck record](results/day16_pose_recheck.json) includes the source
report hash and each saved final position/error.

This is an offline recheck, not 18 new physical attempts. There was no new
simulation or model inference today. The report reader checks emitted
measurements; it does not independently re-observe the world or establish
that those measurements came from trustworthy sensors.

## Preview the protocol

From the existing environment and Isaac Lab directory:

```bash
uv run --no-sync python \
  ../language-guided-robot-manipulation/scripts/day5_evaluate.py --dry_run
```

The ordinary evaluation command still starts fresh table scenes. It is
not the platform-start/no-op protocol added on Day 13.

## What I learned

The controller and the evaluator have different jobs. The controller
checks an action while it runs; the evaluator checks whether the recorded
outcome is consistent enough to count. A small check at the second stage
helps catch regressions without pretending it is another physical test.
