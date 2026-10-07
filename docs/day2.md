# Day 2 — Building a small manipulation scene

## What I wanted to do

After running the official Franka examples on Day 1, I wanted a small scene
that I could change myself. Today's goal was just to set up the workspace:
a Panda arm, a table, a red cube, and a green target platform.

![The custom tabletop scene](images/day2_scene.png)

## What I added

- `scenes/manipulation.py`: the shared scene configuration.
- `scripts/day2_scene.py`: a standalone scene viewer using `AppLauncher`,
  `SimulationContext`, and `InteractiveScene`.
- `scripts/demo_utils.py`: a small helper for saving the actual viewport.

I reused the table and Panda assets from Isaac Lab. The red cube is a 4 cm
box with a mass of 50 g. The green platform is fixed in place and has
collision geometry. For now, the arm stays in its default pose.

The table surface is at `z = 0`, and the ground is at `z = -1.05`. This
matches the official lift example. Keeping these coordinates consistent
should make the next controller step easier.

## How to run it

From the existing environment:

```bash
conda activate robot-demo
cd ~/robotics/IsaacLab
LD_LIBRARY_PATH="$CONDA_PREFIX/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
uv run --no-sync python \
  ../language-guided-robot-manipulation/scripts/day2_scene.py \
  --viz kit --livestream 2
```

For a bounded check and screenshot:

```bash
LD_LIBRARY_PATH="$CONDA_PREFIX/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
uv run --no-sync python \
  ../language-guided-robot-manipulation/scripts/day2_scene.py \
  --viz kit --livestream 2 --max_steps 240 --check \
  --screenshot ../language-guided-robot-manipulation/docs/images/day2_scene.png
```

`uv run --no-sync` uses the working environment without changing its
dependencies. In this setup, Conda provides `uv` and the library path;
the script runs with Isaac Lab's `.venv` Python.

## Checks and problems

The bounded check runs 240 physics steps, checks the Panda's nine joint
positions for finite values, and checks that the cube rests near `z = 0.02`
with small linear and angular velocities. I also inspect the saved image
to check the visible scene.

The check passed with exit code `0`. The cube's final center height was
about `0.017 m`, within the 5 mm tolerance around the expected height.
The saved viewport shows the arm, table, red cube, and green platform.

Two small issues came up:

1. On this Isaac Lab develop checkout, `RigidBodyMaterialBaseCfg` is not
   exported from `isaaclab.sim`. Importing it from its actual material
   configuration module fixed the error.
2. My first settling check combined linear velocity and angular velocity
   into one norm. Those quantities have different units. I changed it to
   separate thresholds: 0.01 m/s and 0.1 rad/s.

`AppLauncher` works but produces a deprecation warning on this checkout.
Kit also prints display/GLFW and PhysX rigid-body lookup warnings in the
remote run. The CPU powersave warning may affect speed. I did not change
the installed environment or Isaac Lab source to silence these messages.

## What this does not do yet

There is no language model, task planner, or autonomous manipulation yet.
The green platform is only a destination for later work. This is a scene
setup check, not a grasping result.

Next I want to connect a simple pick state machine to differential IK
and the gripper, then check whether the cube actually leaves the table.
