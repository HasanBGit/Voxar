# Examples

Eight small, runnable scripts. Each one is under 60 lines, has its command in its docstring, and was run against the real models before it was documented. They need 16 kHz mono 16-bit WAV input (`ffmpeg -i in.m4a -ar 16000 -ac 1 -sample_fmt s16 sample.wav`); no audio yet? Make some with example 03.

| Script | What it shows | Needs |
|---|---|---|
| [`01_transcribe_file.py`](01_transcribe_file.py) | The Python API: one call, one transcript, errors as one line | `voxar[moonshine]` |
| [`02_stream_from_wav.py`](02_stream_from_wav.py) | Live-style streaming: partial text that can change, then a final line | `voxar[moonshine]` |
| [`03_text_to_speech.py`](03_text_to_speech.py) | Saudi-dialect speech to a WAV file | the GPL-3.0 TTS plugin |
| [`04_http_client.py`](04_http_client.py) | Calling `voxar serve` with the standard library, backing off on `503` | `voxar serve` running |
| [`05_websocket_client.py`](05_websocket_client.py) | Live transcript events over a WebSocket, optionally paced like a microphone | `voxar[server]`, `voxar serve` running |
| [`06_mcp_client.py`](06_mcp_client.py) | Launching `voxar mcp` and calling a tool the way an agent host does | `voxar[mcp]` |
| [`07_batch_transcribe.py`](07_batch_transcribe.py) | A folder of WAVs to JSONL, with timing; a bad file is recorded and the batch continues | `voxar[moonshine]` |
| [`08_round_trip.py`](08_round_trip.py) | Say a sentence and transcribe your own speech back | both engines, `ffmpeg` |

## Real output

Everything below is real output from this repository on synthetic Arabic audio (the macOS Arabic voice), not marketing.

**01, a file in, text out**

```text
$ uv run python examples/01_transcribe_file.py customer_service.wav
شكرا لك على إتصالك بخدمة العملاء كيف يمكنني مساعدتك
```

**02, partial text changes, final text does not** (note the partial "السلام علي" revised as more audio arrives)

```text
$ uv run python examples/02_stream_from_wav.py greeting.wav
partial السلام عليكم
partial السلام علي
partial السلام عليكم ورحمة الله
partial السلام عليكم ورحمة الله وبركاته
final   السلام عليكم ورحمة الله وبركاته
```

**07, batch with a broken file in the folder**

```text
$ uv run python examples/07_batch_transcribe.py recordings/ transcripts.jsonl
not a valid WAV file: recordings/broken.wav; convert with: ffmpeg -i INPUT -ar 16000 -ac 1 -sample_fmt s16 OUTPUT.wav
dia0.wav: وشع لومك يا شيخ طيب الحمد لله
msa0.wav: السلام عليكم ورحمة الله وبركاته
```

```json
{"file": "dia0.wav", "seconds": 3.64, "took": 0.26, "rtf": 0.072, "text": "وشع لومك يا شيخ طيب الحمد لله"}
{"file": "msa0.wav", "seconds": 3.99, "took": 0.15, "rtf": 0.037, "text": "السلام عليكم ورحمة الله وبركاته"}
```

**06, an agent host's view of the MCP server**

```text
$ uv run python examples/06_mcp_client.py customer_service.wav
tools: list_engines, speak, transcribe_file
text: {'result': 'شكرا لك على إتصالك بخدمة العملاء كيف يمكنني مساعدتك'}
```

**05, live events over a WebSocket**

```text
$ uv run python examples/05_websocket_client.py meeting.wav
partial الاجتماع غدا الساعة العاشرة
partial الاجتماع غدا الساعة العاشرة صباحا في
partial الاجتماع غدا الساعة العاشرة صباحا في مكتب أرياض
final   الاجتماع غدا الساعة العاشرة صباحا في مكتب أرياض
```

**08, a round trip that is not perfect** (the Saudi voice says it; the recognizer mishears two words)

```text
$ VOXAR_SYNTHESIZER=nabra-saudi uv run python examples/08_round_trip.py "الطقس اليوم حلو والسما صافية مرة"
said:       الطقس اليوم حلو والسما صافية مرة
heard back: أطقس اليوم حلو والسمسافية مرة
```

The transcripts above also show the real quality: "الرياض" came out as "أرياض" and "اتصالك" as "إتصالك". See [Performance](../docs/performance.md) for measured speed and error rates.
