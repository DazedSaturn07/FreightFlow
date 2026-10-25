from pathlib import Path

import pytest

from freightflow.quality import profile_csv


def test_missing_source_is_reported(tmp_path):
    with pytest.raises(FileNotFoundError, match="Required FAF source is missing"):
        profile_csv(tmp_path / "not_downloaded.csv")


def test_repeated_keys_outside_the_profile_sample_are_rejected(tmp_path):
    import csv

    from freightflow.contracts import REQUIRED_COLUMNS

    source = tmp_path / "repeated.csv"
    with source.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(REQUIRED_COLUMNS)
        writer.writerows([[1] * len(REQUIRED_COLUMNS)] * 2)
    with pytest.raises(ValueError, match="repeated full source keys"):
        profile_csv(source, sample_limit=1)


def test_profile_rejects_missing_columns() -> None:
    source = Path("tests/fixtures/missing_columns.csv")
    with pytest.raises(ValueError, match="missing columns"):
        profile_csv(source)
