"""
Tests for OutputWriter.create_run_directory() - specifically, that two runs
within the same second (or even the same microsecond, on a coarser clock)
never collide into the same directory.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from migration.output.writer import OutputWriter


def test_create_run_directory_creates_a_directory_under_output_directory(tmp_path: Path):
    writer = OutputWriter(str(tmp_path))

    run_directory = writer.create_run_directory()

    assert run_directory.is_dir()
    assert run_directory.parent == tmp_path


def test_run_directory_name_has_microsecond_precision(tmp_path: Path):
    """The previous format (%Y%m%d_%H%M%S) had only second-level
    resolution, which is the root cause this fix addresses."""
    writer = OutputWriter(str(tmp_path))

    run_directory = writer.create_run_directory()

    # 20260824_193116_123456 -> date(8) + _ + time(6) + _ + microseconds(6)
    parts = run_directory.name.split("_")
    assert len(parts) >= 3
    assert len(parts[0]) == 8  # YYYYMMDD
    assert len(parts[1]) == 6  # HHMMSS
    assert len(parts[2]) == 6  # microseconds, zero-padded to 6 digits


def test_two_calls_in_the_same_real_second_produce_different_directories(tmp_path: Path):
    """Two back-to-back calls must never land in the same directory, even
    when they fall within the same wall-clock second."""
    writer = OutputWriter(str(tmp_path))

    first = writer.create_run_directory()
    second = writer.create_run_directory()

    assert first != second
    assert first.is_dir()
    assert second.is_dir()


def test_identical_timestamp_falls_back_to_a_numeric_suffix(tmp_path: Path, monkeypatch):
    """Forces the exact same timestamp (simulating a clock with coarser-
    than-microsecond resolution) and proves the numeric-suffix fallback
    still guarantees a distinct directory rather than reusing one."""
    fixed_time = datetime(2026, 8, 24, 19, 31, 16, 123456)

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_time

    monkeypatch.setattr("migration.output.writer.datetime", FrozenDateTime)

    writer = OutputWriter(str(tmp_path))

    first = writer.create_run_directory()
    second = writer.create_run_directory()
    third = writer.create_run_directory()

    assert len({first, second, third}) == 3
    assert first.name == "20260824_193116_123456"
    assert second.name == "20260824_193116_123456_1"
    assert third.name == "20260824_193116_123456_2"
    assert all(p.is_dir() for p in (first, second, third))


def test_many_calls_all_produce_unique_directories(tmp_path: Path, monkeypatch):
    """Stress the suffix fallback with a larger number of frozen-clock calls."""
    fixed_time = datetime(2026, 1, 1, 0, 0, 0, 0)

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return fixed_time

    monkeypatch.setattr("migration.output.writer.datetime", FrozenDateTime)

    writer = OutputWriter(str(tmp_path))
    directories = [writer.create_run_directory() for _ in range(20)]

    assert len(set(directories)) == 20
    assert all(p.is_dir() for p in directories)


def test_output_directory_is_still_created_when_missing(tmp_path: Path):
    """Existing behavior (parents=True) must be preserved."""
    nested = tmp_path / "does" / "not" / "exist" / "yet"
    writer = OutputWriter(str(nested))

    run_directory = writer.create_run_directory()

    assert run_directory.is_dir()
    assert nested.is_dir()
