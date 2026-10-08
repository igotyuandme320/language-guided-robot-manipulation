# Day 11 — Requests with extra constraints

## Goal

The earlier language sets mostly tested object names, basic actions,
negation, and references. I wanted to check additional requirements that
the two-goal interface cannot represent: custom heights, exact placement
regions, continued holding after placement, handover, and conditions.

## Protocol

I wrote [16 labeled requests](../evaluation/language_cases_day11.json)
before running inference: four supported controls and twelve unsupported
requests. Each unsupported label explains the mismatch with the current
scene or controller. For example, the place skill releases at the platform
center; it cannot place on a requested edge and then keep holding the cube.

I kept the Day 6 model snapshot, prompt, examples, and generation settings,
and the Day 7 request checks unchanged. The existing evaluator generated
raw model responses for every case and scored the guarded path separately.
No request in this experiment was sent to the robot executor.

This is a targeted diagnostic set, not a representative estimate of
instruction-following accuracy. It includes familiar rejection categories
as controls, and the supported controls reuse some known templates.

## Results

| Expected behavior | Requests | Rules correct | Raw model correct | Guarded correct |
| --- | --- | --- | --- | --- |
| Supported controls | 4 | 2 | 4 | 4 |
| Reject unsupported request | 12 | 12 | 7 | 8 |
| Total | 16 | 14 | 11 | 12 |

The raw model and guarded entry both falsely accepted three requests:

- Place on the platform and keep holding: it returned an ordinary place
  goal, which would release the cube.
- Pick up and hand to me: it returned pick alone, dropping the handover.
- Place after a door opens: it returned immediate placement, ignoring
  a condition that this scene cannot observe.

The model did correctly refuse the height and above-platform requests in
this set. For left-edge placement it proposed an unsupported target;
schema validation blocked that output, but I did not count it as a
correct semantic refusal. The raw model had two invalid outputs; the
guarded entry had one. All accepted goals in the four supported controls
were correct.

[Complete actual report](results/day11_constraints.json). The guard's zero
false acceptances in Day 7 did not carry over to these different requests.
A matching action and known object names are insufficient to check all
constraints. The strict template baseline rejected every unsupported
request here but missed two supported paraphrases.

No code or model settings changed for this diagnostic. I checked that
the report preserves all 16 cases and the result counts. The existing
85 fast tests remain the last code verification; this milestone does not
add a new controller or claim additional robot trials.

## What I learned

The additional words in a request can change the task even when the main
verb is familiar. A physically successful ordinary place would still be
wrong if continued holding or a waiting condition was requested. These
examples give concrete failure categories for the next request-check
revision, while leaving the original results available for comparison.

## Reproduce the language-only check

```bash
conda activate robot-demo
cd ~/robotics/IsaacLab
uv run --no-sync python \
  ../language-guided-robot-manipulation/scripts/day6_evaluate.py \
  --guarded \
  --cases ../language-guided-robot-manipulation/evaluation/language_cases_day11.json
```

The runner writes a new project-local report. It does not launch Kit or
change controller behavior. Raw output and incorrect rows are retained.
