# Project Rules

Rules for AI agents (e.g. Claude Code) working in this repository.

## Safety & Confirmation

- Never force-push, rewrite history, or delete branches without explicit user confirmation.
- Never run destructive commands (`rm -rf`, `git reset --hard`, `git clean -f`, dropping databases, etc.) without first checking `git status`/current state and confirming with the user.
- Do not commit or push changes unless explicitly asked to.
- Do not bypass hooks or checks (`--no-verify`, disabling linters/tests) to force something to pass.

## Data Handling

- Treat incident data, logs, and any embedded credentials, tokens, or PII as sensitive. Never print, log, or commit secrets.
- Do not send incident data to third-party services (pastebins, external APIs) without explicit user approval.
- Redact or flag sensitive values before including them in commit messages, PR descriptions, or generated reports.

## Code Quality

- Prefer editing existing files over creating new ones.
- Keep changes scoped to the task at hand — no speculative abstractions, unused config, or unrelated refactors.
- Add tests for new logic where a test suite exists; run the existing test suite before declaring a change complete.
- No comments explaining *what* code does; only add comments for non-obvious *why* (edge cases, workarounds, invariants).

## Communication

- Summarize what changed and why at the end of a task, briefly.
- Flag any assumptions made due to missing context instead of guessing silently.
- When a task is ambiguous or has irreversible consequences, ask before proceeding.

## Testing & Verification

- Run relevant tests/build/lint before considering a change complete.
- For any user-facing behavior change, verify it manually (or state clearly that it wasn't possible to verify).
