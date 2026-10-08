# Day 15 — Checking the model worker response

## Goal

The model runs in a separate process so its memory is released before
simulation starts. I found a smaller error-handling gap at that boundary:
the parent parsed the worker's JSON, then indexed `raw_output` directly.
A valid JSON list or an object with missing fields could raise `TypeError`
or `KeyError` instead of a clear input error.

These malformed responses were synthetic test inputs. I did not observe
the actual model worker producing a broken metadata envelope.

## Fix

The parent now validates the entire worker envelope before reading the
model response. It requires exactly the existing metadata fields, the
pinned model/revision on CPU, text for `raw_output`, and a finite,
nonnegative inference duration. Duplicate JSON fields, non-JSON constants,
extra output, and an excessively large integer duration are rejected.

Bad envelopes raise `ValueError` with a worker-response explanation. The
CLI already handles that before launching Kit. A valid envelope still
passes its raw text through the existing strict goal parser. A semantic
model refusal remains `RejectedInstruction`; it is not renamed as a
worker-format error.

This does not address the missing requirements found on Day 14. Valid
metadata and goal schemas cannot prove that the request's meaning was
preserved. The default parser, model prompt, generation, planner, and
controller remain unchanged.

## Verification

I wrote the worker-response tests first and saw them fail on wrong
exception types or on invalid metadata being accepted. The tests replace
only subprocess I/O, then exercise the actual parent validation. Seven
test methods cover valid metadata, malformed structures, identity/field
mismatches, wrong raw-output types, invalid durations, ambiguous JSON,
and semantic refusals. They do not launch or measure a new model.

All 99 fast tests passed after the fix. The pure-Python CI subset contains
73 tests; the new worker checks need no model weights, Torch, or simulator.

I also ran one complete actual model-backed attempt:

```text
Would you please take the red cube into your gripper and hold it?
```

The guarded entry used the real model worker, not the exact-template
branch. The worker took about 9.04 s including model loading and proposed
the valid pick goal. The cube started on the green platform, and the
Franka pick passed the existing physical checks at 1933 manipulation
steps: about 19.84 cm rise and 0.50 s stable hold. The process exited zero.
The [actual execution record](results/day15_worker_execution.json) retains
the raw model output, attribution, measured result, and trace. This is
one normal-path integration check, not a language reliability benchmark.

## Reproduce

With the existing model cache, `robot-demo` environment, and Isaac Lab
directory:

```bash
LD_LIBRARY_PATH="$CONDA_PREFIX/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
uv run --no-sync python \
  ../language-guided-robot-manipulation/scripts/day4_language.py \
  --language_backend guarded \
  --instruction "Would you please take the red cube into your gripper and hold it?" \
  --cube_start green_platform
```

## What I learned

A process boundary has its own format contract, separate from the model's
goal schema. Checking both gives clearer failures while keeping semantic
refusals and malformed responses distinguishable. It is a small software
fix, and I should not present it as improving the model's understanding.
