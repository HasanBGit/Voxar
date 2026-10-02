# AGENTS.md

Instructions for coding agents working in this repo.

- Project: voxar, on-device dialect-aware speech (STT + TTS). Status: pre-alpha. Exists: the core, the Moonshine ASR engine, `models pull`, `listen`, `voxar mcp`, `voxar serve` (with a browser test page), and the Saudi TTS plugin `plugins/voxar-tts-espeak` (GPL-3.0, separate project with its own venv and tooling).
- Never download models or datasets unless the task explicitly says so (the two models were downloaded with the owner's approval). Speed and load measurements are allowed with `scripts/benchmark.py` and `scripts/loadtest.py`; report the hardware with any number, and never quote a number you did not measure.
- Dev commands: `uv sync --extra dev`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, `uv run pytest --cov`. Real-model tests are opt-in: `pytest -m integration`.
- Architecture rules are in `ARCHITECTURE.md` and `docs/adr/`: depend on ports, lazy-import third-party engines, fail fast with actionable errors.
- License rules are strict: read `THIRD_PARTY_LICENSES.md` and `DATA.md` before adding any model, code or data. Do not use components listed under "Deliberately NOT used".
- Do not invent accuracy/speed numbers or claim features that are not implemented.
- Layout: `voxar/` (package; MCP server is `voxar/mcp_server.py`, HTTP server `voxar/server.py`), `tests/`, `scripts/`, `plugins/`, `examples/`, `docs/`.
- Python >= 3.10.
- The plugin's vendored code in `plugins/voxar-tts-espeak/src/voxar_tts_espeak/_vendor/` is third-party: do not reformat or edit it. If a change is unavoidable, update its `MODIFIED` header, `MANIFEST.md` and `UPSTREAM.md` (a test checks the hashes).
- When driving a browser over the DevTools protocol, pick a free port (bind to port 0) and confirm it is yours before sending anything: a fixed port can belong to someone else's browser.
- The core must never import the plugin or any GPL package (CI enforces the license audit).
- MCP rule: stdout is the protocol channel in `voxar mcp`; never print there (logs go to stderr). Any new MCP tool that touches files must go through `resolve_inside`.
- Server rule: keep the Host/Origin guard and the size limits; do not add authentication-less remote defaults (exposed mode requires the token).
