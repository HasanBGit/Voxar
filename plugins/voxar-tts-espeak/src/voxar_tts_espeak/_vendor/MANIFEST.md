| File | Upstream sha256 | Our sha256 | Modification |
|---|---|---|---|
| `arabic_g2p.py` | `7754aab4d0d8e33822ee4f736b641291b6c445608e1df568c12b9762f7c0f55c` | `7754aab4d0d8e33822ee4f736b641291b6c445608e1df568c12b9762f7c0f55c` | none |
| `kokoro/model.py` | `301c55350a068c4ed3b4cbd1209d2afb848bebca72db5657405e47e9dfb604db` | `c2eb0ccec6622f10f2689a07ec31a01600fd69a59b2f5141c33a0df5a936788b` | removed Hugging Face download fallbacks and repo_id |
| `kokoro/modules.py` | `6e14dadc706efc9a8d90e8b4919d45d57342555b242c642cd26f26c65eedc085` | `6e14dadc706efc9a8d90e8b4919d45d57342555b242c642cd26f26c65eedc085` | none |
| `kokoro/istftnet.py` | `3987f169b38d607f41789f536c37fe463b822b699a5b90f8b7f56378bc96c1b5` | `9048b34d658a481328079c1dd89cc1d24ce17625b11d3f6ea6aaef02ee0214ed` | package-relative import of CustomSTFT |
| `kokoro/custom_stft.py` | `94fed3f9ac22bba31135bf8c4ea795762c7ab3ff44f1984d11e7babf27462d69` | `22e24994229b215a0226806e42970e5bf850bfc6e1716664c0ffd3f5c5b6e7fc` | removed unused `from attr import attr` |
