# One-command setup for people who clone the repository. Needs uv: https://docs.astral.sh/uv/
# Without make (for example on Windows), run the commands under each target by hand.

.DEFAULT_GOAL := help
.PHONY: help setup models tts run test check

help:  ## show this list
	@grep -E '^[a-z]+:.*##' $(MAKEFILE_LIST) | sed -E 's/:.*## /\t/'

setup:  ## install voxar with the speech-to-text engine, MCP server, local server and dev tools
	uv sync --inexact --extra moonshine --extra mcp --extra server --extra dev

models:  ## download the speech-to-text model (about 31 MB)
	uv run --no-sync voxar models pull moonshine-tiny-streaming-ar --accept-license

tts:  ## optional: Saudi text-to-speech (GPL-3.0 plugin, large torch install, about 1 GB)
	uv pip install -e plugins/voxar-tts-espeak
	uv run --no-sync voxar models pull nabra-saudi-7m --accept-license

run:  ## start voxar, then open http://127.0.0.1:8765 (after `make tts`: VOXAR_SYNTHESIZER=nabra-saudi make run)
	uv run --no-sync voxar serve

test:  ## run the unit tests (no models needed)
	uv run --no-sync pytest

check:  ## lint, type-check and test
	uv run --no-sync ruff check .
	uv run --no-sync ruff format --check .
	uv run --no-sync mypy
	uv run --no-sync pytest
