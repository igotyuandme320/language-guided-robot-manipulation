# Day 4 — From a language request to verified robot skills

## Goal

On Day 3, I could run pick and place with a command-line flag. Today I
wanted to connect a small language interface to those same skills. I
started with a rule-based parser so I could check each part of the
pipeline before adding a language model.

The current flow is:

```text
supported English/Chinese request → validated goal → symbolic plan
                                 → pick/place skills → IK and gripper → simulation
```

## What I added

`planning/language.py` matches the whole instruction against a few
templates. For example, both “put the red cube on the green platform”
and “把红色方块放到绿色平台上” produce:

```json
{"action": "place", "object": "red_cube", "target": "green_platform"}
```

Some supported examples are:

| Request | Goal |
| --- | --- |
| `Please pick up the red cube.` | Hold the red cube |
| `lift the red block` | Hold the red cube |
| `拿起红色方块` | Hold the red cube |
| `place the red cube onto the green target` | Place it on the green platform |
| `把红色方块放到绿色平台上` | Place it on the green platform |

Unknown colors or destinations, negated requests, and compound requests
are rejected before launching the simulator. This is a limited template
interface, not general language understanding.

`planning/symbolic.py` models three possible cube locations: `table`,
`gripper`, and `green_platform`. Pick requires a supported cube and an
empty gripper. Place requires the cube to be held. A small breadth-first
search finds the shortest legal sequence. From the table, a pick request
needs `[pick]`, while a place request needs `[pick, place]`. If the goal
is already satisfied, the planner returns an empty sequence.

The actual controller loop now lives in `execution/franka.py`, shared by
the Day 3 and Day 4 scripts. It executes the planner's skill calls. I kept
the previous IK, gripper control, and physical success checks.

## Connecting the symbolic state to the scene

After 60 settling steps, `planning/grounding.py` checks the observed cube
pose and velocity to establish the initial symbolic location. Unsupported
heights and moving cubes are rejected rather than guessed to be on the
table. These observations use simulator state, not camera perception.

During execution, reaching a skill phase is still not enough. The cube
must pass the [Day 3 physical checks](day3.md) continuously for 0.5 seconds
before the corresponding symbolic effect is recorded. A timeout exits
with failure and does not record that unfinished skill as successful.

The printed world state is the last verified state. I do not continuously
reclassify it or replan if something changes after a check.

## Results

The Chinese placement command produced this trace in a real simulation
run:

```text
[GOAL] {"action": "place", "object": "red_cube", "target": "green_platform"}
[WORLD] {"cube_location": "table"}
[PLAN] [{"skill": "pick", "object": "red_cube", "target": null}, {"skill": "place", "object": "red_cube", "target": "green_platform"}]
[CHECK] Pick verified: cube_rise=0.1985m; hold=0.50s
[WORLD] {"cube_location": "gripper"}
[WORLD] {"cube_location": "green_platform"}
```

| Run | Plan | Execution steps | Measured result |
| --- | --- | --- | --- |
| Chinese placement request | pick → place | 2554 | Cube center at approximately `(0.50018, -0.21948, 0.04000)` m |
| `Please pick up the red cube.` | pick | 1813 | Cube rose approximately 19.85 cm |
| Previous `day3_pick.py --place` command | pick → place | 2554 | Same final cube coordinates as before the extraction |

All three bounded runs exited with code `0`. The physics timestep is
0.01 s; the counts exclude the initial settling steps. These are
individual default-pose checks, not a success-rate benchmark.

![Rendered result of the Chinese placement command](images/day4_language_place.png)

There are now 35 fast tests covering the skills, parser, goal validation,
planner, initial-state checks, and CLI preview. All passed. Four separate
real-simulator checks also passed: Day 3 timeout, Day 3 interruption,
Day 4 interruption, and Day 4 timeout without a false symbolic effect.
Interruptions exit with code `130`; execution timeouts exit with code `1`.
Test commands are listed in [Day 3](day3.md#running-the-demo).

The GitHub workflow runs syntax checks and the 20 pure-Python parser,
planner, and initial-state tests. It does not run the Torch skills or
launch Isaac Sim. I adjusted the incoming Conda workflow because it
referenced an `environment.yml` that this repository does not have.

## Running it

```bash
conda activate robot-demo
cd ~/robotics/IsaacLab
LD_LIBRARY_PATH="$CONDA_PREFIX/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
uv run --no-sync python \
  ../language-guided-robot-manipulation/scripts/day4_language.py \
  --instruction "把红色方块放到绿色平台上" \
  --viz kit --livestream 2 --keep_open
```

For a bounded run and screenshot, replace `--keep_open` with:

```text
--screenshot ../language-guided-robot-manipulation/docs/images/day4_language_place.png
```

To inspect the goal and plan without launching Kit:

```bash
uv run --no-sync python \
  ../language-guided-robot-manipulation/scripts/day4_language.py \
  --instruction "put the red cube on the green platform" --dry_run
```

The preview explicitly assumes a fresh scene with the cube on the table.
Live runs observe the initial scene instead. Each invocation creates a
fresh scene; this is not a conversation that preserves the previous run.
The timeout defaults remain 3000 steps for pick and 6000 for placement.
The planner supports an already-satisfied goal, although the current CLI
starts with the cube on the table. In that case the executor returns
immediately, even with `--keep_open`.

## What I learned and what is missing

The useful distinction for me was between predicting an action's effect
and checking that it happened. The planner can predict that pick puts
the cube in the gripper, but the executor must actually observe a
successful lift before using that state for the next skill.

This is still one cube, one fixed platform, known object poses, and a
fixed downward grasp. The planner chooses skills; it does not plan arm
paths around obstacles. There is no LLM, learned perception, grasp retry,
or failure recovery. Template parsing keeps the first language baseline
easy to inspect, but does not handle arbitrary wording.

`AppLauncher` still emits a deprecation warning on this develop checkout.
The remote renderer also prints display/GLFW and PhysX lookup warnings,
as on Day 2. I kept the working environment and Isaac Lab source unchanged.

Next I want to measure performance over a small set of starting positions
and keep both successes and failures, before trying a more flexible
language adapter.
