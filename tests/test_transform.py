"""Protect the real failure paths: aggregation, lost leading zeros and invalid data."""

import csv
import shutil
from pathlib import Path

import duckdb
import pytest

from freightflow.config import Settings
from freightflow.contracts import REQUIRED_COLUMNS
from freightflow.transform import build_marts


def example_source(tmp_path, *, tons=1, mode=1):
    config = Settings(tmp_path)
    config.raw_dir.mkdir(parents=True)
    metadata = Path("data/raw/FAF5.7.1/FAF5_metadata.xlsx")
    shutil.copy2(metadata, config.metadata_xlsx)
    with config.source_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        for foreign in ["101", "102"]:
            row = dict.fromkeys(REQUIRED_COLUMNS, 1)
            row.update(fr_orig=foreign, dms_orig="011", dms_dest="019", sctg2="01", dms_mode=mode)
            row.update({f"tons_{year}": tons for year in [2024, 2030, 2050]})
            writer.writerow(row)
    return config


def test_source_rows_are_summed_at_model_grain(tmp_path):
    config = example_source(tmp_path)
    result = build_marts(config)
    assert result["fact_freight_flow"] == 3
    with duckdb.connect() as con:
        frame = con.execute(
            "SELECT * FROM read_parquet(?)",
            [str(config.processed_dir / "fact_freight_flow.parquet")],
        ).df()
    assert set(frame.origin_zone_code) == {"011"}
    assert list(frame.tons_kilotons) == [2, 2, 2]
    assert set(frame.scenario_type) == {"Baseline estimate", "Source forecast scenario"}


def test_negative_values_stop_the_build(tmp_path):
    with pytest.raises(ValueError, match="invalid year-records"):
        build_marts(example_source(tmp_path, tons=-1))


def test_unknown_modes_stop_the_build(tmp_path):
    with pytest.raises(ValueError, match="unknown mode_code"):
        build_marts(example_source(tmp_path, mode=99))


def test_zero_baseline_is_preserved_but_not_ranked(tmp_path):
    config = example_source(tmp_path)
    with config.source_csv.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row["tons_2024"] = 0
    with config.source_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=REQUIRED_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    result = build_marts(config)
    assert result["fact_freight_flow"] == 3
    assert result["mart_lane_priority"] == 0
