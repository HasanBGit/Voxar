# Contributing

voxar is pre-alpha. Issues and discussion are welcome; large pull requests should start with an issue.

## Ground rules

- **Licenses first.** Do not add code, models or data without recording its license in `THIRD_PARTY_LICENSES.md` or `DATA.md`. Non-commercial and share-alike sources need maintainer sign-off.
- **No claims without evidence.** Do not add accuracy or speed numbers to docs unless they are labeled with their source.
- Keep changes small and focused; match the style of the surrounding code.
- Add or update tests for behavior you change.

## Development

Needs [uv](https://docs.astral.sh/uv/) and Python 3.10+.

```bash
uv sync --extra dev        # creates .venv from uv.lock
uv run ruff check .        # lint
uv run ruff format .       # format
uv run mypy                # strict type check
uv run pytest --cov        # unit tests, fails under 85% coverage
```

Real-model integration tests are opt-in (`uv run pytest -m integration`) and need a model download.

Design rules (details in `ARCHITECTURE.md` and `docs/adr/`):
- Core code depends on the interfaces in `voxar.ports`, never on a speech library directly.
- Keep modules small and single-purpose; no copy-pasted logic (one config, one error hierarchy, one model catalog).
- Validate input at the boundary and fail fast with an actionable error.
- Do not add a feature "just in case". Every change should trace to a requirement.
- Never add a runtime dependency with a GPL/AGPL/unknown license to the core (CI enforces this).

Measuring: `scripts/benchmark.py` and `scripts/loadtest.py` (see `docs/performance.md`). Quote only numbers you measured, with the hardware, and say when audio is synthetic. Examples live in `examples/`: keep each one short, runnable, tested against the real model, and listed in `examples/README.md`.

READMEs: `README.md` is the source of truth. `docs/translations/README.ar-SA.md` mirrors it; tests (`tests/test_readme.py`) check that every `voxar` command in either README is accepted by the real CLI, that relative links exist, and that the Arabic code blocks are identical to English ones. Do not add badges, links or claims for things that do not exist yet.

Optional tooling: `pre-commit install` enables ruff, gitleaks and large-file checks on every commit.

By contributing you agree that your contribution is licensed under Apache-2.0.
