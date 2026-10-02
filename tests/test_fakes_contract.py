"""The fakes must satisfy the same contract real engines will."""

from tests.fakes import FakeRecognizer, FakeSynthesizer
from voxar.testing import RecognizerContract, SynthesizerContract


class TestFakeRecognizer(RecognizerContract):
    make_recognizer = FakeRecognizer


class TestFakeSynthesizer(SynthesizerContract):
    make_synthesizer = FakeSynthesizer
