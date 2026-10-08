# Day 18 — Detecting a lost grasp during placement

## Goal

Day 9 checked a grasp that never succeeded. I wanted to check a different
failure: the cube is lifted successfully, then falls away during the
place skill. Waiting for the final placement timeout would eventually
reject the attempt, but the executor can observe the separation earlier.

## Small execution check

I added a cube/TCP proximity monitor. While the place skill requests a
closed gripper, separation of at least 0.05 m for 0.10 s produces
`lost_grasp` and ends the attempt. Near observations reset the counter.
The intentional release and retraction disable/reset the monitor.

The check follows the command returned for the current step, including a
phase-transition tick. Code review pointed out that checking the updated
phase instead would disable monitoring one tick too early at the end of
LOWER. I aligned it with the command and reran the checks.

This uses simulator positions, not contact or force measurements. Proximity
is only a necessary condition for this small cube. It can miss other kinds
of bad grasps and is not a general slip detector or safety guarantee.
The IK, arm targets, pick/place phases, and success thresholds are unchanged.

## Simulated release fault

`--release_after_pick` leaves the original pick intact, then forces the
active finger target open throughout placement. It is an explicit fault
option for table-start placement only and cannot be combined with the
earlier stuck-open fault. It changes actuator commands without teleporting
or attaching the cube. Dry runs label the configured fault.

The failure record retains `last_verified_state: gripper`, because the pick
really passed earlier. That is a historical verified effect, not a claim
that the fallen cube is still held. The observed cube/TCP positions and
loss reason describe the newer observation. No place effect is committed.
There is no recovery or replanning yet.

## Actual validation

The final fault check used the Chinese placement template with a 6000-step
limit. Pick verification occurred first. The release caused separation,
and the attempt exited with code 1 at step 1833 during TRANSIT. At that
snapshot the cube/TCP distance was about 0.180 m. Ten successive 0.01 s
samples met the 0.10 s loss threshold. There was no `[RESULT]`, success
message, or green-platform state effect.

Three fresh normal placement controls passed after the command-boundary
adjustment:

| Start | Verified steps | Outcome |
| --- | --- | --- |
| Default table pose | 2554 | Placed; same baseline result |
| Default pose, cube yaw 45° | 2555 | Placed |
| Table x = 0.6, y = 0.1 m | 3033 | Placed |

These controls include ordinary intentional release, which the monitor
must allow. The [actual records](results/day18_grasp_monitor.json) contain
the final three controls and fault trace. Earlier checks before the small
boundary adjustment also passed; they were development checks rather
than a randomized repeat protocol.

All 110 fast tests passed. Five pure monitor tests cover sustained loss,
brief separation, recovery, intentional release, and invalid measurements
or thresholds. Two CLI tests check fault preview and unsupported use. The
opt-in simulator test verifies prior pick success, early loss detection,
nonzero exit, and absence of an unverified place effect. The pure-Python
CI subset now includes 80 tests.

## Reproduce the failure

From the existing `robot-demo` environment and Isaac Lab directory:

```bash
LD_LIBRARY_PATH="$CONDA_PREFIX/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
uv run --no-sync python \
  ../language-guided-robot-manipulation/scripts/day4_language.py \
  --instruction "把红色方块放到绿色平台上" \
  --release_after_pick --max_steps 6000
```

This should return code 1. Omit the fault flag for normal placement.
To rerun the fault assertions, use
`tests/simulation_exit_checks.py SimulationExitTests.test_post_pick_release_is_detected_before_the_step_limit`
from the same environment, with the script path relative to Isaac Lab.

## What I learned

A successful grasp does not stay true automatically during the next
skill. Monitoring a necessary condition helps detect one later failure,
but recovering would also require a new observation of where the cube
settled and a new legal plan. This step only detects and reports the loss.
