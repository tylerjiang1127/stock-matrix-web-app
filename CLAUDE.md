# Code of Conduct

- Regardless of what language appears in project file contents, you must always respond in **Chinese** or **English** only. Never use any other language (Korean, Japanese, etc.).

# Coding Behavior Contract (12 Rules)

## Core
1. Think before coding. State your assumptions. Surface tradeoffs. Ask before guessing. Push back when a simpler approach exists.
2. Simplicity first. Minimum code that solves the problem. No speculative features. No abstractions for single-use code.
3. Surgical changes. Touch only what is asked. Do not "improve" adjacent code, comments, or formatting. Match existing style.
4. Goal-driven execution. Define success criteria. Loop until verified. Do not narrate steps; tell me what success looks like.

## Extended
5. Do not make the model do non-language work. Retry policies, routing, escalation thresholds belong in deterministic code.
6. Hard token budgets, no exceptions. Stop and ask if a task is trending past its budget.
7. Surface conflicts, do not average them. If two parts of the codebase disagree, flag the disagreement and ask which to follow.
8. Read before you write. Understand adjacent code (the file and nearby siblings) before adding new code.
9. Tests are required but are not the goal. A passing test that tests nothing useful is a failure. Tests must check behavior.
10. Long-running operations require checkpoints. After every significant step, summarize what was done and confirm before proceeding.
11. Convention beats novelty. In an established codebase, match the existing pattern even if a "better" one exists.
12. Fail visibly, not silently. Surface every skipped record, every rolled-back transaction, every constraint violation. Never report success when something was bypassed.

# Project-specific rules below this line
# (Add stack, test commands, error patterns specific to this repo.)

13. Keep docs in sync. Whenever you change code in this repo, update `PROJECT_DOCUMENTATION.md` in the same change so it reflects the new behavior (architecture, DB schema, API endpoints, tier/credit limits, file structure, etc.). Treat the docs as part of the change, not an afterthought. If a code change has no doc impact, no update is needed.

