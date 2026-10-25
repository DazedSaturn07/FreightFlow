"""Deterministic source checks that fail before transformations begin."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from freightflow.contracts import IDENTITY_COLUMNS, REQUIRED_COLUMNS


@dataclass(frozen=True)
class QualityReport:
    source: str
    generated_at_utc: str
    row_count: int
    column_count: int
    missing_required_columns: list[str]
    duplicate_sample_keys: int
    duplicate_full_source_keys: int
    null_rates_sample: dict[str, float]
    numeric_range_sample: dict[str, dict[str, float | None]]
    top_categories_sample: dict[str, list[tuple[str, int]]]
    warnings: list[str]


def sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(chunk_size), b""):
            digest.update(block)
    return digest.hexdigest()


def write_manifest(source: Path, target: Path, row_count_if_known: int | None = None) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source_name": "Freight Analysis Framework FAF5.7.1",
        "source_url": "https://faf.ornl.gov/faf5/data/download_files/FAF5.7.1.zip",
        "license_or_terms_url": "https://www.bts.gov/faf/faf5",
        "verified_at_utc": datetime.now(UTC).isoformat(),
        "retrieved_at_utc": None,
        "files": [
            {
                "path": source.name,
                "bytes": source.stat().st_size,
                "sha256": sha256(source),
                "row_count_if_known": row_count_if_known,
            }
        ],
        "notes": "Supplied local snapshot; original retrieval time is unknown. Raw source is immutable and excluded from version control because of size.",
    }
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _rate(value: int, total: int) -> float:
    return round(value / total, 6) if total else 0.0


def profile_csv(path: Path, sample_limit: int = 100_000) -> QualityReport:
    """Profile a bounded sample while counting every physical CSV row."""
    if not path.exists():
        raise FileNotFoundError(f"Required FAF source is missing: {path}")

    with path.open("r", encoding="utf-8", newline="") as source:
        reader = csv.DictReader(source)
        fieldnames = reader.fieldnames or []
        missing = sorted(set(REQUIRED_COLUMNS).difference(fieldnames))
        if missing:
            raise ValueError(f"Source contract failed; missing columns: {', '.join(missing)}")

        row_count = 0
        sampled = 0
        nulls: Counter[str] = Counter()
        categories = {
            column: Counter()
            for column in ("dms_orig", "dms_dest", "dms_mode", "sctg2", "trade_type")
        }
        numeric_columns = (
            "tons_2024",
            "tons_2030",
            "tons_2050",
            "value_2024",
            "value_2030",
            "value_2050",
        )
        numeric_values = {column: [] for column in numeric_columns}
        keys: Counter[tuple[str, ...]] = Counter()

        for row in reader:
            row_count += 1
            if sampled >= sample_limit:
                continue
            sampled += 1
            for column in fieldnames:
                if row[column] in (None, ""):
                    nulls[column] += 1
            for column, counter in categories.items():
                counter[row[column]] += 1
            keys[tuple(row[column] or "" for column in IDENTITY_COLUMNS)] += 1
            for column in numeric_columns:
                try:
                    numeric_values[column].append(float(row[column]))
                except (TypeError, ValueError):
                    pass

    with duckdb.connect() as connection:
        identity = ",".join(IDENTITY_COLUMNS)
        full_duplicates = connection.execute(
            f"SELECT COUNT(*)-COUNT(DISTINCT ({identity})) FROM read_csv_auto(?)", [str(path)]
        ).fetchone()[0]
    if full_duplicates:
        raise ValueError(
            f"Source contains {full_duplicates} repeated full source keys. Review before aggregation."
        )

    ranges = {
        column: {"min": min(values) if values else None, "max": max(values) if values else None}
        for column, values in numeric_values.items()
    }
    warnings = []
    if any(value > 0 for value in (nulls[column] for column in IDENTITY_COLUMNS)):
        warnings.append(
            "Some source identity columns are blank in the profiled sample; foreign-route fields can be expected blanks for domestic flows."
        )
    return QualityReport(
        source=path.name,
        generated_at_utc=datetime.now(UTC).isoformat(),
        row_count=row_count,
        column_count=len(fieldnames),
        missing_required_columns=missing,
        duplicate_sample_keys=sum(count - 1 for count in keys.values() if count > 1),
        duplicate_full_source_keys=full_duplicates,
        null_rates_sample={column: _rate(nulls[column], sampled) for column in fieldnames},
        numeric_range_sample=ranges,
        top_categories_sample={
            column: counter.most_common(10) for column, counter in categories.items()
        },
        warnings=warnings,
    )


def save_profile(report: QualityReport, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
