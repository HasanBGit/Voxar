# Vendored third-party code

Origin: Hugging Face model repo `oddadmix/Nabra-Saudi-7M`, commit `ef45d882f20355767190dffb2a34393ed1df74fa` (2026-09-18).

| Component | Original author | License | Where |
|---|---|---|---|
| `kokoro/*` (patched Kokoro network) | hexgrad (Kokoro), patched by oddadmix (Nabra) | Apache-2.0 | `LICENSES/Apache-2.0.txt` |
| parts of `kokoro/istftnet.py`, `kokoro/modules.py` | Aaron (Yinghao) Li, StyleTTS2 | MIT | `LICENSES/MIT-StyleTTS2.txt` |
| `arabic_g2p.py` | oddadmix (Nabra) | Apache-2.0 (per the model card) | `LICENSES/Apache-2.0.txt` |

We vendor instead of fetching code at runtime so no remote code is ever executed. Files were reviewed on 2026-10-02: no process spawning, `eval`/`exec`, sockets or pickle; weights load with `torch.load(weights_only=True)`; all network fallbacks removed.

Modified files carry a `MODIFIED` header (Apache-2.0 section 4(b)). `MANIFEST.md` records the upstream and current SHA-256 of each file; a test fails if a vendored file changes without the manifest being updated. The runtime pieces these files import (`misaki`, `phonemizer-fork`, `espeakng-loader`) are separate packages.
