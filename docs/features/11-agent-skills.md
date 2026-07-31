# Feature 11: Agent Skills Framework

Builds out `agents/skills/` — scaffolded but empty since the folder-structure pass — into a working framework for packaging domain expertise as data (`SKILL.md` files) rather than hardcoding it into agent prompts, plus three example skills and a real integration point in the pipeline.

## What was built

- **`SKILL.md` format** — YAML front matter (metadata + trigger conditions) followed by a Markdown body (guidance + required `## Examples` section).
- **`app/agents/skills/models.py`** — `SkillMetadata` (name, version, description, author, triggers), with a strict `MAJOR.MINOR.PATCH` version validator; `SkillTriggers` (keywords + regex patterns); `Skill` (metadata + parsed content + source path).
- **`app/agents/skills/parser.py`** — `parse_skill_markdown()`: splits front matter from body, validates the YAML, and requires a `## Examples` section to be present.
- **`app/agents/skills/loader.py`** — `SkillLoader`: discovers every `*/SKILL.md` under `library/`, parses and validates each, resolves same-name version conflicts (higher version wins, loser recorded in `shadowed_skills`), and exposes `.match(text)`, `.get(name)`, `.all_skills()`. `get_skill_loader()` is a cached FastAPI dependency; `SkillLoader.from_skills(...)` supports building one from in-memory skills for tests.
- **Three example skills** (`agents/skills/library/`): `python`, `fastapi`, `log_analysis` — see `ARCHITECTURE.md` → "Agent Skills framework" for what each covers.
- **Pipeline integration**: Root Cause is now `make_root_cause_agent(llm, skill_loader)` — it matches skills against the raw logs and appends any matched guidance to its prompt under "Relevant domain expertise". `build_investigation_graph()`, `run_investigation()`, and all four `/investigations*` endpoints were updated to thread `skill_loader` through.

See `ARCHITECTURE.md` → "Agent Skills framework" for the full design and why Root Cause is the one agent augmented.

## How to run it

No new setup — skills load automatically from the bundled library. Requires `ANTHROPIC_API_KEY`/`GEMINI_API_KEY` the same as before (skills only add prompt content to an existing LLM call, they don't remove that requirement):

```bash
cd backend
uv sync
uv run uvicorn app.main:app --app-dir src --reload
```

Inspect the loaded library directly:

```bash
uv run python -c "
from app.agents.skills.loader import SkillLoader
loader = SkillLoader()
loader.load()
for s in loader.all_skills():
    print(s.metadata.name, s.metadata.version)
print('matches for a traceback:', [s.metadata.name for s in loader.match('Traceback (most recent call last):')])
"
```

## How to test it

```bash
cd backend
uv run pytest -v
uv run ruff check .
```

## Verification performed

- `uv run pytest -v` — 69/69 passing, including:
  - `tests/unit/test_skill_loader.py` (13 new tests) — front-matter/body parsing, rejection of missing front matter, invalid YAML, and a missing `## Examples` section; malformed version rejected; version-tuple parsing; keyword matching via `from_skills`; version-conflict resolution (higher wins, in either load order); `SkillLoadError` on a malformed on-disk file; and — loading the **real bundled library** — all three skills present, no name collisions, every skill has valid semver/description/`## Examples`, the `python` skill matches a real traceback, and none of the three match clean logs.
  - `tests/unit/test_root_cause_agent.py` (2 new tests) — matched skill content is appended to the LLM prompt; when nothing matches, that content is absent.
  - `tests/unit/test_investigation_graph.py` — updated to pass the real `SkillLoader` through `build_investigation_graph()`, demonstrating genuine end-to-end integration rather than a mocked-out dependency.
- `uv run ruff check .` — clean.
- **Live smoke test**: `POST /api/v1/investigations` with a real Python traceback correctly reached Root Cause (past the deterministic Monitoring/Log Analysis stages) and failed with the expected `503` (no LLM key configured) — confirming the skill-loader dependency resolves correctly through the real FastAPI DI chain without needing a key itself. `/openapi.json` still generates correctly with the added dependency.

## Decisions worth calling out

- **Trigger matching is deliberately soft, not an exclusive router.** A log matching both `fastapi` and `python` triggers (realistic, since FastAPI errors are backed by Python tracebacks) is expected and correct — matched skills only add optional context to one prompt, they don't gate which agent runs.
- **`## Examples` is structurally enforced**, not left to convention — a skill missing it fails to load, mirroring how the rest of this pipeline refuses malformed structured input rather than accepting it silently.
- **Only Root Cause consumes skills.** Monitoring/Log Analysis are deterministic parsers with nothing for a skill to augment; Recommendation/Report work from Root Cause's output, one step removed from the raw logs where trigger matching happens. Wiring skills into every agent "for completeness" would have been exactly the kind of scope inflation this project avoids.
- **No multi-version-directory scheme.** Each skill declares one version; conflicts are resolved by comparison, not by a directory-per-version layout — appropriate for three skills with one version each, extensible later if a real need for coexisting versions shows up.

## What's next

Per the original roadmap: MCP integration, guardrails, and evaluation remain pending, plus log upload & storage (Feature 2). A natural extension once real usage exists: more skills (other languages/frameworks, specific vendor error catalogs) and, if warranted, wiring skill matching into Recommendation too.
