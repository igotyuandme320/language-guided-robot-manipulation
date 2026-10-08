# Day 20 — Sampling initial poses with a fixed seed

## Goal

The old evaluation used nine fixed positions, and the rotation check used
one position. I wanted a small check that changes both position and yaw
without adjusting the grasp controller to individual cases.

## Protocol

The existing batch runner now accepts `--random_poses` and `--seed`.
It samples x in [0.4, 0.6] m, y in [-0.1, 0.1] m, and yaw in [-45, 45]
degrees independently and uniformly, rounding to six decimal places.
Each sampled pose gets the same English and Chinese placement templates.
The default command still runs the original 18-case grid.

I froze four poses with seed 20 before launching simulation. Three happened
to have x near 0.581 m, so this small sample does not cover the region
evenly. I kept the seed and all cases. Each language/pose case starts a
fresh scene, uses the rule parser, and has the existing 6000-step and
120-second process limits. There is no model inference or fault injection.
The scene, skills, IK, gripper control, and verification thresholds stay
the same.

The runner saves configured poses, actual scene quaternion observations,
execution traces, and failures. `--limit` selects a prefix of the generated
protocol for a smoke check; omitting it runs all selected cases.

## Actual results

All eight fresh-scene placement attempts passed. Both language templates
gave the same measured result within each pair:

| Sample | x (m) | y (m) | Yaw (degrees) | Steps per attempt | Final horizontal error (mm) |
| --- | --- | --- | --- | --- | --- |
| 1 | 0.581128 | 0.037251 | 23.985833 | 2818 | 2.207 |
| 2 | 0.580923 | -0.048035 | 12.215328 | 2621 | 0.713 |
| 3 | 0.580989 | 0.074426 | 6.564660 | 2925 | 3.066 |
| 4 | 0.433876 | -0.017695 | 44.445421 | 2674 | 0.755 |

The maximum horizontal placement error was about 3.07 mm. I checked that
the settled initial positions and quaternions matched the configured
cases: maximum horizontal deviation was about 0.00125 mm and maximum yaw
deviation was about 0.000039 degrees. These are simulator measurements,
not camera estimates.

The [full report](results/day20_seeded_poses.json) retains all eight rows,
traces, protocol, timestamps, and source/log hashes. The raw console and
logs stay locally under `.cache/day20/`. There were no failed cases to
exclude. The protocol snapshot predates the first simulation, and no
controller adjustment or seed change followed the results.

All 119 fast tests passed. Four new tests cover seeded pairing and bounds,
prefix limits, invalid counts/limits, and retaining the scene observation.
The preview and trace checks first failed before implementation. The
pure-Python CI subset has 89 tests. A separate code review found no
blocking issue. Existing AppLauncher deprecation warnings remain; this
stage does not change the simulator launch pattern.

## Reproduce

From the existing `robot-demo` environment and Isaac Lab checkout:

```bash
LD_LIBRARY_PATH="$CONDA_PREFIX/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
uv run --no-sync python \
  ../language-guided-robot-manipulation/scripts/day5_evaluate.py \
  --random_poses 4 --seed 20 --dry_run
```

Remove `--dry_run` to execute all eight attempts. The runner prints a new
report path under the project cache. To preview just the first pair, add
`--limit 2`. This seed reproduces the configured poses; it does not promise
identical physics or timing across simulator versions and hardware.

The actual run also used
`--output ../language-guided-robot-manipulation/.cache/day20/seed20`.
That directory now exists; choose a new output directory for a rerun to
preserve the earlier logs.

## What I learned

Saving a seed is useful, but the actual case list is the experiment I need
to preserve. Two equivalent language templates at one pose are paired
checks, not two independent samples of the workspace. Changing x, y, and
yaw together also means this experiment cannot isolate their individual
effects.
