"""Measure voxar on THIS machine: speed, memory, start-up cost and (optionally) error rates.

    python scripts/benchmark.py asr  clips/*.wav [--refs refs.json] [--repeat 3]
    python scripts/benchmark.py tts  "نص أول" "نص ثان" [--repeat 3]

Results describe the machine you run it on, nothing else: report the hardware with the numbers.
Real-time factor (RTF) is processing time divided by audio duration; below 1.0 is faster than
real time. ``refs.json`` maps a clip's file stem to its reference text and enables WER/CER.
Reference-based error rates are only as meaningful as the audio: synthetic speech says little
about real speech.
"""

import argparse
import json
import os
import platform
import re
import statistics
import sys
import time
import wave
from collections.abc import Sequence
from pathlib import Path

try:
    import resource  # Unix only
except ImportError:  # Windows
    resource = None  # type: ignore[assignment]

from voxar import Config, Voxar
from voxar.audio import write_wav

_DIACRITICS = re.compile("[ً-ْـ]")
_NOT_WORD = re.compile(r"[^\w\s]")


def normalize(text: str) -> str:
    """Arabic normalization used for scoring: no diacritics/punctuation, unified letter forms."""
    text = _DIACRITICS.sub("", text)
    text = re.sub("[إأآ]", "ا", text).replace("ة", "ه").replace("ى", "ي")
    return re.sub(r"\s+", " ", _NOT_WORD.sub(" ", text)).strip()


def edit_distance(a: Sequence[str], b: Sequence[str]) -> int:
    previous = list(range(len(b) + 1))
    for i, item in enumerate(a, 1):
        current = [i]
        for j, other in enumerate(b, 1):
            cost = 0 if item == other else 1
            current.append(min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + cost))
        previous = current
    return previous[-1]


def error_rates(reference: str, hypothesis: str) -> tuple[float, float]:
    """(WER, CER) in percent after normalization."""
    ref, hyp = normalize(reference), normalize(hypothesis)
    words = 100 * edit_distance(ref.split(), hyp.split()) / max(1, len(ref.split()))
    chars = 100 * edit_distance(list(ref), list(hyp)) / max(1, len(ref))
    return words, chars


def percentile(values: Sequence[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(p / 100 * (len(ordered) - 1)))]


def peak_memory() -> str:
    if resource is None:
        return "n/a on this platform"
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    megabytes = peak / (1024 * 1024) if sys.platform == "darwin" else peak / 1024
    return f"{megabytes:.0f} MB"


def duration_s(path: Path) -> float:
    with wave.open(str(path), "rb") as handle:
        return handle.getnframes() / handle.getframerate()


def machine() -> str:
    system = f"{platform.platform()}, {platform.machine()}"
    return f"{system}, {os.cpu_count()} cores, Python {platform.python_version()}"


def bench_asr(clips: list[Path], refs: dict[str, str], repeat: int) -> None:
    started = time.perf_counter()
    app = Voxar.from_config(Config.from_env(os.environ))
    first = app.transcribe(clips[0])  # engine creation + model load happen inside this call
    cold = time.perf_counter() - started
    print(f"machine: {machine()}")
    print(f"cold start (first transcription incl. engine and model load): {cold:.2f} s\n")
    rtfs, wers, cers, total_audio, total_wall = [], [], [], 0.0, 0.0
    print(f"{'clip':14s}{'audio s':>8s}{'wall s':>8s}{'RTF':>7s}{'WER %':>8s}{'CER %':>8s}")
    for clip in clips:
        length = duration_s(clip)
        for _ in range(repeat):
            t0 = time.perf_counter()
            text = app.transcribe(clip)
            wall = time.perf_counter() - t0
            rtfs.append(wall / length)
            total_audio += length
            total_wall += wall
        wer = cer = float("nan")
        if clip.stem in refs:
            wer, cer = error_rates(refs[clip.stem], text)
            wers.append(wer)
            cers.append(cer)
        print(f"{clip.stem:14s}{length:8.2f}{wall:8.2f}{wall / length:7.3f}{wer:8.1f}{cer:8.1f}")
    print(
        f"\nwarm RTF: mean {statistics.mean(rtfs):.3f}, median {statistics.median(rtfs):.3f}, "
        f"p95 {percentile(rtfs, 95):.3f} over {len(rtfs)} runs"
    )
    print(f"throughput: {total_audio / total_wall:.1f} audio seconds per wall second")
    if wers:
        print(
            f"error rates (n={len(wers)} clips): "
            f"mean WER {statistics.mean(wers):.1f} %, mean CER {statistics.mean(cers):.1f} %"
        )
    print(f"peak memory: {peak_memory()}   (first result: {first[:40]!r})")


def bench_tts(texts: list[str], repeat: int) -> None:
    started = time.perf_counter()
    app = Voxar.from_config(Config.from_env(os.environ))
    app.speak(texts[0])  # engine creation + model load happen inside this call
    cold = time.perf_counter() - started
    print(f"machine: {machine()}")
    print(f"cold start (first synthesis incl. engine and model load): {cold:.2f} s\n")
    print(f"{'chars':>6s}{'audio s':>9s}{'wall s':>8s}{'RTF':>7s}")
    rtfs = []
    for text in texts:
        for _ in range(repeat):
            t0 = time.perf_counter()
            audio = app.speak(text)
            wall = time.perf_counter() - t0
            seconds = len(audio.pcm) / 2 / audio.sample_rate
            rtfs.append(wall / seconds)
        print(f"{len(text):6d}{seconds:9.2f}{wall:8.2f}{wall / seconds:7.3f}")
    print(
        f"\nwarm RTF: mean {statistics.mean(rtfs):.3f}, median {statistics.median(rtfs):.3f}, "
        f"p95 {percentile(rtfs, 95):.3f} over {len(rtfs)} runs"
    )
    print(f"peak memory: {peak_memory()}")
    if os.environ.get("BENCH_SAVE"):
        write_wav(os.environ["BENCH_SAVE"], audio)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    sub = parser.add_subparsers(dest="kind", required=True)
    asr = sub.add_parser("asr")
    asr.add_argument("clips", nargs="+", type=Path)
    asr.add_argument("--refs", type=Path, help="JSON: file stem -> reference text")
    asr.add_argument("--repeat", type=int, default=1)
    tts = sub.add_parser("tts")
    tts.add_argument("texts", nargs="+")
    tts.add_argument("--repeat", type=int, default=1)
    args = parser.parse_args(argv)
    if args.kind == "asr":
        refs = json.loads(args.refs.read_text()) if args.refs else {}
        bench_asr(args.clips, refs, args.repeat)
    else:
        bench_tts(args.texts, args.repeat)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
