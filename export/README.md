# export

ONNX export scripts for the models voxar uses. **Planned (milestone M2); nothing is implemented yet.**

Why it matters: the Saudi text-to-speech plugin needs torch today, which rules out low-end devices. An ONNX export is the planned route to them. Any export must keep the model's license and the pinned-SHA-256 download flow (`voxar/models.py`), and must be recorded in `THIRD_PARTY_LICENSES.md` first.
