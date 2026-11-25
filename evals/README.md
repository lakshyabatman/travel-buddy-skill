# Evals

`cases.yaml` holds 15 prompts and the behaviour each one should show. They are generic.
They are not a personal trip.

Before a release:

1. `python evals/run.py --check` to confirm the file is well formed.
2. `python evals/run.py` and run each prompt against the agent you are about to ship.
3. Tick `SCORE.md`. A case fails if any shared rule or any of its own `must` lines fail.
4. Do not ship a release that books, transfers points, or invents a fare. Fix the skill or
   record the failure. This runner does not call a model and does not invent a score.

CI runs only `--check`.
