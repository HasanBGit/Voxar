# Threat model (draft)

Method: lightweight STRIDE per asset. Scope: the voxar library, CLI, MCP server, optional local server, and the release pipeline. Status: draft for v0.1; revisit before each release.

## Assets
1. **User audio and transcripts** (may be personal data).
2. **Model files** (integrity matters: a tampered model or loader can run code or change output).
3. **Software supply chain** (dependencies, CI, release artifacts).

## Threats and mitigations

| # | Threat | Asset | Mitigation |
|---|---|---|---|
| T1 | Tampered or swapped model download | Models | **Implemented:** the catalog pins the artifact URL (revision in the path) and a SHA-256 per file; `voxar models pull` streams over HTTPS only (no other scheme), writes to a `.part` file, verifies the hash before moving it into place, and deletes it on mismatch; every engine start re-verifies. Weakness: hashes were measured from the first download, so they pin what we saw, not an upstream-signed value |
| T2 | Code execution through a pickle-based weight file (`.pth`) | Models | Never `pickle.load` model files; load with `weights_only=True` or convert to ONNX/safetensors; the TTS plugin documents this |
| T3 | Malicious or vulnerable dependency | Supply chain | Lockfile; `pip-audit` and Dependabot; `dependency-review` on PRs; weekly scheduled scan |
| T4 | Compromised CI | Supply chain | Actions pinned by commit SHA; read-only workflow tokens; no secrets in CI; Dependabot keeps the pinned actions current |
| T5 | Secrets committed | Supply chain | gitleaks in pre-commit and CI; `.gitignore` blocks weights/audio |
| T6 | Audio leaves the device | Audio | No telemetry; the network is used only by the explicit `models pull` and by `voxar llm`, which sends text (never audio) to the chosen provider; offline mode blocks both remote use cases; documented. The browser test page loads its fonts from public CDNs (the font request, not audio, goes out; it falls back to system fonts offline) |
| T7 | Local server or MCP reachable by other machines or by a web page | Audio | **Implemented:** `voxar serve` binds to 127.0.0.1 and refuses other addresses without `--allow-remote` (then every request needs a random per-start token, as a Bearer header or a SameSite=Strict cookie; still plain HTTP, so the token can be sniffed); requests with a non-loopback `Host` get 403 and WebSocket upgrades with a foreign `Origin` or `Host` are closed (DNS rebinding); uploads capped at 50 MB, streams at 1 h, one inference job at a time per engine with at most 8 waiting (further requests get 503 with Retry-After), and at most 4 live streams (a fifth is told why and closed with 1013). MCP runs over stdio only (no network). |
| T8 | Hostile audio input (malformed files) crashes or exhausts memory | Availability | Validate format and size at the boundary; bounded queues; decode with maintained libraries; fail with typed errors |
| T9 | Third-party license violation (GPL in core) | Legal | License-audit CI job; ADR 0002 |
| T10 | An agent reads or overwrites arbitrary files through MCP tools | Files | **Implemented:** MCP paths must resolve (symlinks and `..` included) inside allowed directories (default: the working directory); `speak` never overwrites unless `overwrite=true`; only WAV audio is read |
| T11 | An LLM API key leaks (logs, errors, redirects, committed files) | Secrets | **Implemented:** keys come from environment variables only; they travel in a request header, are removed from error messages, and redirects are refused so a key is never resent to another host; plain http is refused except for loopback; the repo's gitleaks check covers committed files |
| T12 | An agent (or text injected into its context) listens through the microphone or speaks unprompted | Audio | **Implemented:** the voice tools exist only with `--voice`; the microphone opens only during a `listen`/`ask` call, for at most 60 s, returns the transcript only and keeps no audio; one voice call at a time; spoken text capped at 500 characters. **Residual:** a client that auto-approves tool calls lets an agent listen whenever it likes, so approve `listen` and `ask` deliberately |
| T13 | Audio that is not the user (other people, a video, a prank) becomes an instruction for a coding agent through the voice inbox | Agent control | **Implemented:** the default is push-to-talk (nothing is recorded until Enter); `--always-on` prints a warning and supports `--wake WORD`; every message is delivered to the agent labeled as automatically transcribed with a reminder to confirm risky actions aloud; messages are capped at 2000 characters and read once. **Residual:** an always-on listener without a wake word, next to an agent whose tool calls are auto-approved, can be steered by anyone who can be heard |

## Out of scope for v0.1
Authentication and multi-user serving, adversarial audio attacks on recognition quality, hosted deployment.

## Reporting
See `SECURITY.md`.
