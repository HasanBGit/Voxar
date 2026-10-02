# export

ONNX export scripts for the models voxar uses. Nothing is implemented here yet.

The Saudi text-to-speech plugin needs torch today, which rules out low-end devices; an ONNX export is the intended route to them. Any export must keep the model's license and the pinned-SHA-256 download flow (`voxar/models.py`), and be recorded in `THIRD_PARTY_LICENSES.md` first.
