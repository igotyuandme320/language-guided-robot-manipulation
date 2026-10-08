# Day 8 — Recording the manipulation demo

## Goal

The screenshots only showed the final state. I wanted a short motion clip
so someone visiting the repository can see the cube being picked up,
moved, released, and left on the platform.

## Implementation

I added optional `--record_gif` to the language entry script. It uses the
real Kit viewport, with an initial frame, one request every 50 controller
steps, and a final frame after verified success. With `dt=0.01`, the
regular requests are 0.5 s apart. Capture requests run during normal
simulation updates; the code waits for remaining captures at the end.

Pillow, which was already installed in the Isaac Lab environment, combines
the screenshots into a 720 × 405 GIF. No new packages were installed.
The JSON next to the GIF stores the original request, actual model
response, goal, physical result, requested frame steps, and phases. Raw
PNG files stay in the project's ignored `.cache/day8/` directory.

Frames can lag the requested step because rendering happens separately.
Playback durations use the nominal controller steps and include a 2 s
final hold. This is sampled visualization, not a measurement of real-time
robot speed. No motion is synthesized between captured frames.

A failed task does not publish the GIF or its success metadata. Existing
GIF/JSON targets are protected. If an ordinary output write fails, the
code removes only files created by that attempt. I added tests for a
metadata collision, failed copy, and preservation of an existing clip.

## Result and checks

The recorded request was “Please relocate the red cube onto the green
target.” The guarded entry used the actual model, which produced a place
goal. The planner ran pick followed by place, and the sustained physical
checks passed at step 2554. The final cube center was near
`(0.50018, -0.21948, 0.04000)` m. The process exited with code `0`.

![Actual manipulation recording](images/day8_manipulation.gif)

The GIF contains 53 frames, is about 6.3 MB, and plays for 27.54 s including
the final hold. I decoded every frame and checked the duration against the
[recording metadata](images/day8_manipulation.json). I also inspected
snapshots from approach, lift, transfer, lowering, and the final state.
The two recording runs produced the same physical result at this pose.

All 84 fast tests passed; 63 pure-Python tests run in GitHub CI. The
recording checks cover preflight rejection, output protection, and failed
publication cleanup. One additional real-rendered check limited an
attempt to one step: it returned failure and published neither a GIF nor
JSON success metadata. Ordinary controller parameters were unchanged.

## Running it

The pinned Day 6 model should already be cached. From the existing setup:

```bash
conda activate robot-demo
cd ~/robotics/IsaacLab
LD_LIBRARY_PATH="$CONDA_PREFIX/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
uv run --no-sync python \
  ../language-guided-robot-manipulation/scripts/day4_language.py \
  --language_backend guarded \
  --instruction "Please relocate the red cube onto the green target." \
  --viz kit --livestream 2 \
  --record_gif ../language-guided-robot-manipulation/.cache/day8/my_demo.gif
```

Choose a new project-local `.gif` path. Recording requires an actual Kit
viewport. Omit `--record_gif` to use the ordinary runner. With
`--language_backend rules` and the standard placement template, the same
recorder also works without loading a model.

## What I learned

A clip is useful for showing the behavior, but it is not enough to prove
success. I kept the physical checks and saved their result alongside the
images. The clip covers one request and one starting position; the Day 5
grid and Day 7 language reports answer different questions.
