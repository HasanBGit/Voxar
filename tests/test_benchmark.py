"""The benchmark's scoring helpers are pure functions: test them, so the numbers can be trusted."""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "benchmark", Path(__file__).parent.parent / "scripts" / "benchmark.py"
)
assert spec and spec.loader
benchmark = importlib.util.module_from_spec(spec)
spec.loader.exec_module(benchmark)


def test_normalize_removes_diacritics_punctuation_and_unifies_letters() -> None:
    assert benchmark.normalize("السَّلامُ عَلَيْكُم، كيف حالُك؟") == "السلام عليكم كيف حالك"
    assert benchmark.normalize("أحمد إبراهيم آمن") == "احمد ابراهيم امن"
    assert benchmark.normalize("مدرسة على") == "مدرسه علي"


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [("", "", 0), ("abc", "abc", 0), ("abc", "abd", 1), ("abc", "", 3), ("kitten", "sitting", 3)],
)
def test_edit_distance(a: str, b: str, expected: int) -> None:
    assert benchmark.edit_distance(list(a), list(b)) == expected


def test_error_rates_are_zero_for_equivalent_text_and_scaled_otherwise() -> None:
    assert benchmark.error_rates("السلام عليكم.", "السلام عليكم") == (0.0, 0.0)
    wer, cer = benchmark.error_rates("كيف حالك اليوم", "كيف نحالك اليوم")
    assert wer == pytest.approx(100 / 3)  # one of three words is wrong
    assert 0 < cer < wer


def test_percentile_picks_the_expected_rank() -> None:
    values = [5.0, 1.0, 3.0, 2.0, 4.0]
    assert benchmark.percentile(values, 0) == 1.0
    assert benchmark.percentile(values, 50) == 3.0
    assert benchmark.percentile(values, 100) == 5.0
