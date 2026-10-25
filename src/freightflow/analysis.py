"""Evidence-backed findings and cross-artifact reconciliation."""

from __future__ import annotations

import csv
from pathlib import Path

import duckdb

from freightflow.config import Settings


def _path(path: Path) -> str:
    return str(path).replace("'", "''")


def reconcile(settings: Settings) -> Path:
    """Reconcile the KPI mart against the same source aggregation independently."""
    source = _path(settings.source_csv)
    mart = _path(settings.processed_dir / "mart_kpi_summary.parquet")
    output = settings.quality_dir / "reconciliation.csv"
    settings.quality_dir.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect()
    query = f"""
    WITH source_totals AS (
      SELECT 2024 AS year, CAST(trade_type AS INTEGER) AS trade_type_code,
             SUM(CAST(tons_2024 AS DOUBLE)) AS tons_kilotons,
             SUM(CAST(value_2024 AS DOUBLE)) AS value_musd,
             SUM(CAST(tmiles_2024 AS DOUBLE)) AS tmiles_million
      FROM read_csv_auto('{source}', header=true, sample_size=100000)
      GROUP BY 2
      UNION ALL
      SELECT 2030, CAST(trade_type AS INTEGER), SUM(CAST(tons_2030 AS DOUBLE)), SUM(CAST(value_2030 AS DOUBLE)), SUM(CAST(tmiles_2030 AS DOUBLE))
      FROM read_csv_auto('{source}', header=true, sample_size=100000) GROUP BY 2
      UNION ALL
      SELECT 2050, CAST(trade_type AS INTEGER), SUM(CAST(tons_2050 AS DOUBLE)), SUM(CAST(value_2050 AS DOUBLE)), SUM(CAST(tmiles_2050 AS DOUBLE))
      FROM read_csv_auto('{source}', header=true, sample_size=100000) GROUP BY 2
    ), published AS (
      SELECT year, trade_type_code, tons_kilotons, value_musd, tmiles_million FROM read_parquet('{mart}')
    )
    SELECT s.year, s.trade_type_code, 'tons_kilotons' AS metric, s.tons_kilotons AS source_value, p.tons_kilotons AS published_value, s.tons_kilotons-p.tons_kilotons AS difference
    FROM source_totals s JOIN published p USING (year, trade_type_code)
    UNION ALL
    SELECT s.year, s.trade_type_code, 'value_musd', s.value_musd, p.value_musd, s.value_musd-p.value_musd FROM source_totals s JOIN published p USING (year, trade_type_code)
    UNION ALL
    SELECT s.year, s.trade_type_code, 'tmiles_million', s.tmiles_million, p.tmiles_million, s.tmiles_million-p.tmiles_million FROM source_totals s JOIN published p USING (year, trade_type_code)
    ORDER BY 1, 2, 3
    """
    rows = connection.execute(query).fetchall()
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "year",
                "trade_type_code",
                "metric",
                "source_value",
                "published_value",
                "difference",
                "status",
            ]
        )
        for row in rows:
            # Aggregations run through separate physical query plans. A one-millionth
            # tolerance accepts floating-point order effects without masking a material gap.
            writer.writerow([*row, "PASS" if abs(row[-1]) < 1e-6 else "FAIL"])
    connection.close()
    if len(rows) != 27 or any(abs(row[-1]) >= 1e-6 for row in rows):
        raise ValueError(
            f"KPI reconciliation failed. Inspect {output.name} before publishing reports."
        )
    return output


def write_findings(settings: Settings) -> Path:
    """Write concise observations from computed, not hand-authored, results."""
    lane = _path(settings.processed_dir / "mart_lane_priority.parquet")
    kpi = _path(settings.processed_dir / "mart_kpi_summary.parquet")
    output = settings.export_dir / "executive_findings.csv"
    settings.export_dir.mkdir(parents=True, exist_ok=True)
    connection = duckdb.connect()
    total_2024, total_2050 = connection.execute(
        f"SELECT SUM(CASE WHEN year=2024 THEN tons_kilotons END), SUM(CASE WHEN year=2050 THEN tons_kilotons END) FROM read_parquet('{kpi}')"
    ).fetchone()
    lanes = connection.execute(
        f"""SELECT origin_zone_code, destination_zone_code, mode_code, cagr_2024_2050,
                   high_growth_lane_index
            FROM read_parquet('{lane}')
            WHERE tons_2024_kilotons >= 1000 AND mode_code BETWEEN 1 AND 6
            ORDER BY high_growth_lane_index DESC
            LIMIT 3"""
    ).fetchall()
    connection.execute(
        f"""COPY (
            SELECT origin_zone_code, destination_zone_code, mode_code, tons_2024_kilotons,
                   cagr_2024_2050, high_growth_lane_index,
                   CASE
                     WHEN mode_code >= 7 THEN 'Review: other, unknown or no domestic mode'
                     WHEN tons_2024_kilotons < 1000 THEN 'Review: low baseline can inflate CAGR'
                     ELSE 'Review: validate capacity and commodity mix'
                   END AS exception_reason
            FROM read_parquet('{lane}')
            WHERE mode_code >= 7 OR (tons_2024_kilotons < 1000 AND cagr_2024_2050 > 0.20)
            ORDER BY high_growth_lane_index DESC
            LIMIT 100
        ) TO '{_path(settings.export_dir / "excel_exceptions.csv")}' (HEADER)"""
    )
    connection.execute(
        f"""COPY (
            SELECT m.mode_code, d.mode_name, m.tons_kilotons, m.value_musd, m.mode_share
            FROM read_parquet('{_path(settings.processed_dir / "mart_mode_mix.parquet")}') m
            LEFT JOIN read_parquet('{_path(settings.processed_dir / "dim_mode.parquet")}') d USING (mode_code)
            WHERE m.year = 2024 AND m.trade_type_code = 1
            ORDER BY m.tons_kilotons DESC
        ) TO '{_path(settings.export_dir / "mode_mix_2024.csv")}' (HEADER)"""
    )
    connection.close()
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["finding_type", "evidence", "interpretation", "recommended_next_step"])
        writer.writerow(
            [
                "Network scenario growth",
                f"Total tons are {total_2024:,.1f} ktons in 2024 and {total_2050:,.1f} ktons in the FAF source forecast scenario.",
                "This is a scenario comparison, not a guaranteed outcome.",
                "Stress-test the top corridors with capacity, cost, and service data before acting.",
            ]
        )
        for origin, destination, mode, cagr, score in lanes:
            writer.writerow(
                [
                    "High-growth lane candidate",
                    f"Lane {origin} to {destination}, mode {mode}, has CAGR {cagr:.2%} and index {score:.3f}.",
                    "The index combines growth and value density; it is a prioritization screen, not an optimization recommendation.",
                    "Validate operational feasibility and commodity mix for this lane.",
                ]
            )
    return output
