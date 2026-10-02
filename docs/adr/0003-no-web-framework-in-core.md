# ADR 0003: No web or UI framework in the core

Status: accepted and implemented (2026-10-02): `voxar[server]` (FastAPI + uvicorn + websockets) and `voxar[mcp]` are optional extras; the core has no runtime dependencies

## Context
The target is low-end devices and one-command installs. Most users need a library and a CLI, not a server or a UI.

## Decision
- Core: plain Python (>=3.10), stdlib dataclasses and Protocols, `argparse` CLI. No runtime dependencies beyond what an engine needs.
- Optional extra `voxar[server]`: FastAPI + uvicorn for streaming to browser/mobile clients over WebSocket/HTTP. Bound to localhost by default.
- No frontend framework and no build step. A single static test page (`voxar/ui/index.html`) ships with `voxar[server]` and is served at `/`; it is a test tool, not a product UI. No public hosted demo exists.

## Consequences
- Small installs and fast start on small devices.
- Frameworks stay out until a use case justifies them (YAGNI).
- Flask and Django were rejected: weak async/WebSocket support and too heavy, respectively.
