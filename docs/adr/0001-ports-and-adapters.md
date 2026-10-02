# ADR 0001: Ports and adapters for engines

Status: accepted (2026-10-02)

## Context
Speech engines change fast (Moonshine, sherpa-onnx, whisper.cpp, new Saudi fine-tunes). We want to swap or add engines without touching the rest of the code, and we want most code to be testable without models.

## Decision
The core defines small `typing.Protocol` interfaces (ports). Each engine is an adapter in its own module that implements a port. The core finds engines through entry points and never imports a speech library directly.

## Consequences
- Adding an engine means adding a module and registering it; the core is unchanged (open/closed).
- Unit tests use fakes; one contract-test suite proves each adapter honours the port.
- A little indirection cost. We keep it small: no plugin framework beyond entry points.
