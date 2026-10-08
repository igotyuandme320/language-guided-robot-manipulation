# Day 12 — Rejecting known unsupported follow-up requirements

## Goal

Day 11 exposed three requests that could reach an ordinary robot goal
while dropping part of the instruction. I added explicit checks for those
known unsupported requirements, keeping the model and controller unchanged.

## Changes

The guarded entry now rejects handover phrases, unavailable door/condition
references, continued holding combined with placement, and explicit edge
or corner placement. These are literal domain restrictions. The existing
place skill releases at the platform center, so it cannot meet those extra
requirements. The checks reject instead of editing the proposed goal.

Tests include English/Chinese variants and controls for holding in the
robot's hand and picking before placement. An initial handover pattern
also rejected “Hold the red cube in your hand for me.” I tightened that
pattern and kept the sentence as a regression case.

The rule backend remains the default. The ordinary goal schema, planner,
skills, IK, model prompt, and generation settings are unchanged.

## Saved-response replay

I rescored the exact 16 raw responses from Day 11 using the revised checks.
The [new report](results/day12_guard_replay.json) retains the old guarded
predictions, new predictions, raw outputs, and unchanged labels. It records
`inference_rerun: false`: there was no new model inference or robot trial.

| Check on the same saved responses | Before | After |
| --- | --- | --- |
| Correct guarded decisions | 12/16 | 16/16 |
| False acceptances | 3 | 0 |

The edge-placement request was already blocked by goal validation; now it
receives an explicit guard refusal. The other three previously accepted
requests are refused before model inference in the live entry. These are
known development examples, so this replay is not independent evidence of
language generalization or reliable handling of other constraints.

I also replayed the two Day 7 reports: both remain at 21/24. New literal
patterns can still reject valid wording or miss other unsupported details.
The underlying model's Day 11 score remains 11/16; this change does not
make the model better.

## Verification

All 89 fast tests passed, including three actual CLI refusal cases with a
0.01 s model deadline. The refusals came from request checks rather than
model timeout, and Kit did not start. The pure-Python CI subset has 66 tests.
The positive hint tests do not establish new model or physical performance.
There was no controller change requiring another physical placement trial.

## Reproduce the replay

From Isaac Lab with the existing `robot-demo` environment:

```bash
uv run --no-sync python \
  ../language-guided-robot-manipulation/scripts/day12_rescore.py
```

The script writes a new project-local report directory. It reads the
committed Day 11 responses and does not load model weights. To rerun
inference instead, use the Day 11 evaluator command with the current code;
that evaluates the revised guard. The original Day 11 baseline was recorded
with commit `7bc4550` before these changes.

## What I learned

A specific failure can motivate a small fix, but measuring the fix on the
same examples mostly checks implementation. A broader evaluation still
needs new requests and clear labels. I kept the pre-fix result and made
the replay explicit so it does not look like a new model benchmark.
