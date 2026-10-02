"""Load-test a running ``voxar serve``. Needs the server extra (websockets) for the stream mode.

    python scripts/loadtest.py http --file clip.wav --concurrency 8 --requests 40
    python scripts/loadtest.py speak --text "مرحبا" --concurrency 4 --requests 20
    python scripts/loadtest.py ws   --file clip.wav --streams 6 [--realtime]

It reports what happened on the machine you ran it on (success/failure counts, latency
percentiles, throughput). It is a measuring tool, not a pass/fail gate, and it never sends
anything except the audio or text you give it.
"""

import argparse
import asyncio
import http.client
import json
import sys
import threading
import time
import wave
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).parent))
from benchmark import percentile  # noqa: E402  (shared helper; path set up just above)


def summarize(latencies: list[float]) -> str:
    if not latencies:
        return "no successful requests"
    return (
        f"latency s: min {min(latencies):.3f}  p50 {percentile(latencies, 50):.3f}  "
        f"p95 {percentile(latencies, 95):.3f}  max {max(latencies):.3f}"
    )


def post(url: str, path: str, body: bytes, content_type: str) -> tuple[int, float]:
    parts = urlsplit(url)
    conn = http.client.HTTPConnection(parts.hostname, parts.port, timeout=300)
    started = time.perf_counter()
    try:
        conn.request("POST", path, body=body, headers={"Content-Type": content_type})
        response = conn.getresponse()
        response.read()
        return response.status, time.perf_counter() - started
    except OSError:
        return 0, time.perf_counter() - started  # 0 = connection-level failure
    finally:
        conn.close()


def run_http(
    url: str, path: str, body: bytes, content_type: str, concurrency: int, total: int
) -> dict:
    latencies: list[float] = []
    statuses: Counter[int] = Counter()
    lock = threading.Lock()

    def one(_: int) -> None:
        status, took = post(url, path, body, content_type)
        with lock:
            statuses[status] += 1
            if status == 200:
                latencies.append(took)

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        list(pool.map(one, range(total)))
    wall = time.perf_counter() - started
    return {"wall": wall, "statuses": dict(statuses), "latencies": latencies}


def audio_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as handle:
        return handle.getnframes() / handle.getframerate()


async def one_stream(url: str, pcm: bytes, realtime: bool, frame_ms: int = 100) -> dict:
    import websockets

    frame = 16_000 * 2 * frame_ms // 1000
    started = time.perf_counter()
    result = {"refused": False, "first_text_s": None, "final_after_end_s": None, "events": 0}
    try:
        async with websockets.connect(url, open_timeout=30) as ws:

            async def reader() -> None:
                async for message in ws:
                    data = json.loads(message)
                    result["events"] += 1
                    if result["first_text_s"] is None and data.get("text"):
                        result["first_text_s"] = time.perf_counter() - started

            read_task = asyncio.create_task(reader())
            for i in range(0, len(pcm), frame):
                await ws.send(pcm[i : i + frame])
                if realtime:
                    await asyncio.sleep(frame_ms / 1000)
            sent_at = time.perf_counter()
            await ws.send("end")
            await read_task
            result["final_after_end_s"] = time.perf_counter() - sent_at
    except Exception as exc:  # noqa: BLE001 - a load tester must record every failure kind
        result["refused"] = True
        result["error"] = f"{type(exc).__name__}: {str(exc)[:60]}"
    return result


async def run_streams(url: str, pcm: bytes, streams: int, realtime: bool) -> list[dict]:
    return await asyncio.gather(*(one_stream(url, pcm, realtime) for _ in range(streams)))


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    sub = parser.add_subparsers(dest="mode", required=True)
    for name in ("http", "speak"):
        p = sub.add_parser(name)
        p.add_argument("--url", default="http://127.0.0.1:8765")
        p.add_argument("--concurrency", type=int, default=4)
        p.add_argument("--requests", type=int, default=20)
        if name == "http":
            p.add_argument("--file", type=Path, required=True)
        else:
            p.add_argument("--text", required=True)
    ws = sub.add_parser("ws")
    ws.add_argument("--url", default="ws://127.0.0.1:8765/v1/stream")
    ws.add_argument("--file", type=Path, required=True)
    ws.add_argument("--streams", type=int, default=4)
    ws.add_argument("--realtime", action="store_true", help="pace frames at 1x real time")
    args = parser.parse_args(argv)

    if args.mode == "http":
        body = args.file.read_bytes()
        seconds = audio_seconds(args.file)
        out = run_http(
            args.url, "/v1/transcribe", body, "audio/wav", args.concurrency, args.requests
        )
        ok = len(out["latencies"])
        print(
            f"transcribe: {args.requests} requests, concurrency {args.concurrency}, "
            f"clip {seconds:.1f} s"
        )
        print(f"statuses: {out['statuses']}   wall {out['wall']:.1f} s")
        print(
            f"throughput: {ok / out['wall']:.2f} req/s = "
            f"{ok * seconds / out['wall']:.1f} audio s per wall s"
        )
        print(summarize(out["latencies"]))
    elif args.mode == "speak":
        body = json.dumps({"text": args.text}).encode()
        out = run_http(
            args.url, "/v1/speak", body, "application/json", args.concurrency, args.requests
        )
        ok = len(out["latencies"])
        print(f"speak: {args.requests} requests, concurrency {args.concurrency}")
        print(f"statuses: {out['statuses']}   wall {out['wall']:.1f} s")
        print(f"throughput: {ok / out['wall']:.2f} req/s")
        print(summarize(out["latencies"]))
    else:
        with wave.open(str(args.file), "rb") as handle:
            pcm = handle.readframes(handle.getnframes())
        started = time.perf_counter()
        results = asyncio.run(run_streams(args.url, pcm, args.streams, args.realtime))
        wall = time.perf_counter() - started
        served = [r for r in results if not r["refused"]]
        print(
            f"ws: {args.streams} concurrent streams of {len(pcm) / 32000:.1f} s audio, "
            f"realtime={args.realtime}"
        )
        print(
            f"served {len(served)}, refused/failed {len(results) - len(served)}   wall {wall:.1f} s"
        )
        for r in results:
            if r["refused"]:
                print(f"  refused: {r['error']}")
        print(
            "first text after s:",
            summarize([r["first_text_s"] for r in served if r["first_text_s"]]),
        )
        print(
            "final after end  s:",
            summarize([r["final_after_end_s"] for r in served if r["final_after_end_s"]]),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
