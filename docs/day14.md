# Day 14 — New requests after the known constraint fixes

## Goal

Day 12 replayed examples used to develop the checks. I wanted to try new
wording and extra requirements without adding another fix first. I froze
16 hand-written requests and labels before running the same CPU model:
four supported controls and twelve requests outside the current domain.

This is another small diagnostic, not a statistically independent test
set. I wrote it knowing the system's limitations. Some examples vary the
known handover, continued-grip, corner, and door requirements; others add
timing, speed, repetition, route, or grasp-face requirements.

## Protocol

The code baseline was `5042bd4`. I kept the model revision, prompt,
examples, generation settings, rule parser, and checks unchanged. The
existing evaluator generated a new raw model response for every request,
even when the rule or guard branch could decide without a model call.
No simulator or robot execution was launched.

The [case file](../evaluation/language_cases_day14.json) includes the label
reason for every request. The [actual report](results/day14_constraints.json)
retains all raw responses, predictions, generation times, prompt/settings,
and the case-file hash recorded before inference. Labels and requests
remained unchanged throughout the run.

## Results

| Front end | Correct supported goals | Correct refusals | Overall | False acceptances |
| --- | --- | --- | --- | --- |
| Rules | 2/4 | 12/12 | 14/16 | 0 |
| Raw model | 3/4 | 9/12 | 12/16 | 3 |
| Guarded entry | 4/4 | 10/12 | 14/16 | 2 |

The raw model also produced one invalid response: an extra closing brace
after the goal for `lift the red block`. That counts as an incorrect
supported prediction, not a deliberate refusal. The guarded entry used
the exact rule template for that request and did not inherit this error.

The existing checks blocked the four variants of known requirements.
Two other requests still became ordinary goals:

- `Put the red cube on the green platform within five seconds.` became
  a placement goal with no deadline. The controller does not represent or
  guarantee that requested time bound.
- `Grab the red cube by its bottom face and hold it.` became a pick goal
  with no grasp-face selection. The skill has a fixed downward approach.

The raw model's third false acceptance was the Chinese placement followed
by continued gripping; the guard rejected that known contradiction.
For the other unsupported requests, the combined branch refused them in
this run. That does not establish reliable recognition of their variants.

Rules and the guarded entry have the same overall score here but different
errors. Rules missed two valid paraphrases; the guarded entry accepted all
four supported requests but lost two requirements. The set contains more
rejection cases than supported cases, so the overall count alone would
hide that difference.

## Verification and reproduction

I checked all 16 stored rows against the frozen case file, recomputed the
scores from the saved predictions, and compared the model settings/prompt
with Day 11. The eight language-evaluation tests passed. There was no
production-code or controller change needing another physical trial.

From the existing `robot-demo` environment and Isaac Lab directory:

```bash
uv run --no-sync python \
  ../language-guided-robot-manipulation/scripts/day6_evaluate.py \
  --cases ../language-guided-robot-manipulation/evaluation/language_cases_day14.json \
  --guarded
```

The evaluator chooses a new project-local report directory by default.
Exit code zero means the comparison completed; incorrect predictions stay
in the report and are not converted into passing outcomes.

## What I learned

Adding patterns for observed failures helps those categories, but it does
not make a general requirement checker. A valid goal can still lose a
deadline or a grasp constraint. For the outreach demo I should show these
limits beside the successful motion, and keep the template entry as the
default while studying a better way to handle unsupported requirements.
