"""Measure how well voice capture ends a phrase: volume gate versus Silero, with and without noise.

    python scripts/turntaking.py clips/*.wav [--noise 0 200 800] [--silence 1.0] [--repeat 5]

Each clip (16 kHz mono 16-bit WAV) is placed after 1 s of background noise and followed by 4 s of
noise, then fed to ``record_utterance`` 100 ms at a time, as the microphone would. Per condition:

  missed       the phrase was never captured
  cut early    capture stopped before the speaker finished
  end delay    seconds from the end of speech to the end of capture (ideal: the silence setting)
  false start  capture "found" a phrase in noise alone (a stream with no speech at all)

Noise is white, so it is a stand-in for steady room noise, nothing more. Results describe the clips
you give it: with synthetic speech they test the plumbing, not real people. Silero is used when
installed (``voxar[vad]`` and ``voxar models pull silero-vad``); otherwise only the volume gate
runs.
"""
# ruff: noqa: S311  (seeded noise for repeatable measurements, not security)

import argparse
import os
import random
import statistics
import sys
import wave
from array import array
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from voxar.config import Config
from voxar.domain import AudioChunk
from voxar.vad import detector_factory
from voxar.voice import SpeechTest, record_utterance

RATE = 16_000
BLOCK_S = 0.1
LEAD_S = 1.0
TAIL_S = 4.0
_BLOCK_BYTES = int(RATE * BLOCK_S) * 2


@dataclass(frozen=True)
class Outcome:
    captured: bool
    stopped_at_s: float  # how much of the stream was consumed when capture ended


def read_clip(path: Path) -> bytes:
    with wave.open(str(path), "rb") as handle:
        if (handle.getframerate(), handle.getnchannels(), handle.getsampwidth()) != (RATE, 1, 2):
            raise ValueError(f"{path}: need 16 kHz mono 16-bit WAV")
        return handle.readframes(handle.getnframes())


def noise_pcm(seconds: float, rms: float, rng: random.Random) -> array:
    samples = array("h")
    for _ in range(int(RATE * seconds)):
        samples.append(max(-32768, min(32767, round(rng.gauss(0.0, rms)))))
    return samples


def add_noise(speech: bytes, rms: float, rng: random.Random) -> bytes:
    """The speech with white noise of the given RMS mixed in."""
    samples = array("h")
    samples.frombytes(speech)
    mixed = array("h", (max(-32768, min(32767, round(s + rng.gauss(0.0, rms)))) for s in samples))
    return mixed.tobytes()


def build_stream(speech: bytes | None, noise_rms: float, rng: random.Random) -> tuple[bytes, float]:
    """Noise, then the speech (if any), then noise. Returns the audio and when speech ends (s)."""
    lead = noise_pcm(LEAD_S, noise_rms, rng).tobytes()
    tail = noise_pcm(TAIL_S, noise_rms, rng).tobytes()
    body = add_noise(speech, noise_rms, rng) if speech else b""
    return lead + body + tail, LEAD_S + len(body) / 2 / RATE


def run_once(stream: bytes, silence_s: float, is_speech: SpeechTest | None) -> Outcome:
    consumed = 0

    def blocks() -> Iterator[AudioChunk]:
        nonlocal consumed
        for start in range(0, len(stream), _BLOCK_BYTES):
            consumed += 1
            yield AudioChunk(pcm=stream[start : start + _BLOCK_BYTES])

    audio = record_utterance(
        blocks(), max_seconds=60.0, silence_seconds=silence_s, is_speech=is_speech
    )
    return Outcome(audio is not None, consumed * BLOCK_S)


@dataclass(frozen=True)
class Summary:
    runs: int
    missed: int
    cut_early: int
    false_starts: int
    noise_runs: int
    median_delay_s: float | None


def summarize(
    with_speech: list[tuple[Outcome, float]], noise_only: list[Outcome], tolerance_s: float = 0.05
) -> Summary:
    """``with_speech`` pairs each outcome with the time its speech ended."""
    captured = [(o, end) for o, end in with_speech if o.captured]
    delays = [o.stopped_at_s - end for o, end in captured if o.stopped_at_s >= end - tolerance_s]
    return Summary(
        runs=len(with_speech),
        missed=len(with_speech) - len(captured),
        cut_early=sum(1 for o, end in captured if o.stopped_at_s < end - tolerance_s),
        false_starts=sum(1 for o in noise_only if o.captured),
        noise_runs=len(noise_only),
        median_delay_s=statistics.median(delays) if delays else None,
    )


def measure(
    clips: list[bytes],
    noise_rms: float,
    silence_s: float,
    repeat: int,
    new_test: Callable[[], SpeechTest] | None,
    seed: int = 0,
) -> Summary:
    rng = random.Random(seed)
    with_speech: list[tuple[Outcome, float]] = []
    noise_only: list[Outcome] = []
    for _ in range(repeat):
        for clip in clips:
            stream, speech_end = build_stream(clip, noise_rms, rng)
            with_speech.append(
                (run_once(stream, silence_s, new_test() if new_test else None), speech_end)
            )
        stream, _ = build_stream(None, noise_rms, rng)
        noise_only.append(run_once(stream, silence_s, new_test() if new_test else None))
    return summarize(with_speech, noise_only)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("clips", nargs="+", type=Path)
    parser.add_argument("--noise", nargs="+", type=float, default=[0.0, 200.0, 800.0])
    parser.add_argument("--silence", type=float, default=1.0)
    parser.add_argument("--repeat", type=int, default=3)
    args = parser.parse_args(argv)

    clips = [read_clip(path) for path in args.clips]
    detectors: dict[str, Callable[[], SpeechTest] | None] = {"volume": None}
    silero = detector_factory(Config.from_env(os.environ))
    if silero is not None:
        detectors["silero"] = silero
    else:
        print("silero not set up (voxar[vad] + models pull silero-vad): measuring volume only\n")

    print(f"{len(clips)} clip(s), {args.repeat} repeat(s), silence setting {args.silence:g} s")
    print(
        f"{'noise rms':>9s} {'detector':8s} {'missed':>9s} {'cut early':>10s} "
        f"{'end delay':>10s} {'false start':>12s}"
    )
    for rms in args.noise:
        for name, factory in detectors.items():
            s = measure(clips, rms, args.silence, args.repeat, factory)
            delay = "n/a" if s.median_delay_s is None else f"{s.median_delay_s:.2f} s"
            print(
                f"{rms:9.0f} {name:8s} {s.missed:>4d}/{s.runs:<4d} {s.cut_early:>5d}/{s.runs:<4d} "
                f"{delay:>10s} {s.false_starts:>6d}/{s.noise_runs:<5d}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
