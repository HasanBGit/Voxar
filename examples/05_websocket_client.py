"""Stream a WAV file to `voxar serve` over a WebSocket and print live transcript events.

    uv run python examples/05_websocket_client.py sample.wav [--realtime]

Needs the server extra (websockets). Frames are binary 16 kHz mono 16-bit PCM; a text frame
ends the stream. With --realtime the file is sent at the speed of speech, like a microphone.
"""

import asyncio
import json
import sys
import wave

import websockets

URL = "ws://127.0.0.1:8765/v1/stream"
FRAME_BYTES = 3200  # 100 ms of 16 kHz 16-bit mono


async def main(path: str, realtime: bool) -> None:
    with wave.open(path, "rb") as handle:
        pcm = handle.readframes(handle.getnframes())
    async with websockets.connect(URL) as ws:

        async def send() -> None:
            for start in range(0, len(pcm), FRAME_BYTES):
                await ws.send(pcm[start : start + FRAME_BYTES])
                if realtime:
                    await asyncio.sleep(0.1)
            await ws.send("end")

        sender = asyncio.create_task(send())
        async for message in ws:
            event = json.loads(message)
            print(
                event.get("error") or ("final  " if event["final"] else "partial"),
                event.get("text", ""),
            )
        await sender


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--realtime"]
    if len(args) != 1:
        sys.exit(__doc__)
    asyncio.run(main(args[0], "--realtime" in sys.argv))
