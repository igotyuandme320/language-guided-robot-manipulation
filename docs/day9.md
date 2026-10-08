# Day 9 — Checking a failed grasp

## Goal

The successful demo does not show whether the executor can detect a bad
grasp. I tried a simple simulated fault: keep the gripper open while the
arm follows the ordinary pick skill. I wanted to check that entering the
LIFT phase would not be counted as grasping the cube.

## Implementation

The optional `--gripper_stuck_open` flag keeps the active finger target at
0.04 m. It does not change the arm targets, IK, physics, or goal parser.
The flag is printed when active and appears in dry-run output. Ordinary
runs keep the original finger commands.

When the execution loop reaches its step limit or the app closes without
verified success, it prints a structured `[FAILURE]` before raising the
existing error. The record includes the goal, plan, active skill/phase,
step count, observed cube/TCP/finger positions, cube rise, and the last
verified symbolic state. That state is deliberately separate from the
latest observed pose: it records the initial observation or most recent
verified skill effect.

This is a simulated command fault, not a model of a particular hardware
failure. The structured record covers bounded loop exits. Startup errors,
Ctrl+C, and non-finite physics exceptions still use the existing exception
paths; I have not made a complete fault-monitoring system.

## Results

All runs started with the cube at the same default tabletop position and
used the rule parser. The fault attempts had a 3000-step limit.

| Run | Observed result | Exit code |
| --- | --- | --- |
| Normal pick | verified at 1813 steps; rise about 19.85 cm | 0 |
| Pick with open-gripper fault | reached LIFT; cube stayed on table; no verified effect | 1 |
| Place with open-gripper fault | failed in the pick skill; place never started | 1 |

In both fault runs, the active finger position was about 0.04 m. The TCP
rose to about 0.217 m, while the cube center remained near 0.017 m. Its
measured rise was effectively zero. The stable-success counter remained
zero, and the only emitted world state was `table`. There was no success
result, no `gripper` or `green_platform` effect, and no placement command.

The [actual control and failure records](results/day9_fault_check.json)
retain these results. This is one artificial fault at one starting pose,
not a broad robustness or recovery benchmark. There is no automatic retry.

All 85 fast tests passed. The new opt-in simulator test ran both fault
requests and checked their nonzero exits, observations, and absence of
symbolic commits. The normal physical control also passed with the same
result as the earlier pick run. The app-closed branch is implemented but
has not received a separate zero-step close test.

## Running the fault check

```bash
conda activate robot-demo
cd ~/robotics/IsaacLab
LD_LIBRARY_PATH="$CONDA_PREFIX/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
uv run --no-sync python \
  ../language-guided-robot-manipulation/scripts/day4_language.py \
  --instruction "put the red cube on the green platform" \
  --gripper_stuck_open --max_steps 3000
```

This command should fail with code `1`. Omit the fault flag for ordinary
execution. To repeat the assertions for both pick and place:

```bash
LD_LIBRARY_PATH="$CONDA_PREFIX/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
uv run --no-sync python \
  ../language-guided-robot-manipulation/tests/simulation_exit_checks.py \
  SimulationExitTests.test_stuck_open_gripper_does_not_commit_symbolic_effects
```

The test prints its project-local raw-log directory.

## What I learned

The arm can reach its desired pose while the object stays behind. The
skill phase describes what the controller is trying to do. Observing the
cube is necessary before recording a successful symbolic effect. This
small counterexample makes that distinction clearer than another
successful placement run.
