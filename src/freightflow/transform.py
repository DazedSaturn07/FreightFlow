"""DuckDB transformations: raw FAF remains wide; published marts are long and governed."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pandas as pd

from freightflow.config import Settings
from freightflow.contracts import BASELINE_YEAR, YEARS


def _csv_path(path: Path) -> str:
    return str(path).replace("'", "''")


def _source_relation(source: Path) -> str:
    return f"read_csv_auto('{_csv_path(source)}', header=true, sample_size=100000)"


def _long_source(source: Path) -> str:
    relation = _source_relation(source)
    selects = []
    for year in YEARS:
        scenario = "'Baseline estimate'" if year == BASELINE_YEAR else "'Source forecast scenario'"
        selects.append(
            f"""
            SELECT
              lpad(CAST(dms_orig AS VARCHAR), 3, '0') AS origin_zone_code,
              lpad(CAST(dms_dest AS VARCHAR), 3, '0') AS destination_zone_code,
              lpad(CAST(sctg2 AS VARCHAR), 2, '0') AS commodity_code,
              CAST(dms_mode AS INTEGER) AS mode_code,
              CAST(trade_type AS INTEGER) AS trade_type_code,
              {year} AS year,
              {scenario} AS scenario_type,
              CAST(tons_{year} AS DOUBLE) AS tons_kilotons,
              CAST(value_{year} AS DOUBLE) AS value_musd,
              CAST(tmiles_{year} AS DOUBLE) AS tmiles_million
            FROM {relation}
            """
        )
    return " UNION ALL ".join(selects)


def _write_dimension(frame: pd.DataFrame, destination: Path) -> int:
    frame.to_parquet(destination, index=False)
    frame.to_csv(destination.with_suffix(".csv"), index=False)
    return len(frame)


def build_dimensions(settings: Settings) -> dict[str, int]:
    """Extract source-owned labels before they are joined in presentation tools."""
    if not settings.metadata_xlsx.exists():
        raise FileNotFoundError(f"Missing FAF metadata workbook: {settings.metadata_xlsx}")
    zone = pd.read_excel(settings.metadata_xlsx, sheet_name="FAF Zone (Domestic)")
    commodity = pd.read_excel(settings.metadata_xlsx, sheet_name="Commodity (SCTG2)")
    mode = pd.read_excel(settings.metadata_xlsx, sheet_name="Mode")
    trade = pd.read_excel(settings.metadata_xlsx, sheet_name="Trade Type")
    dimensions = {
        "dim_zone": pd.DataFrame(
            {
                "zone_code": zone["Numeric Label"].astype(int).astype(str).str.zfill(3),
                "zone_name": zone["Short Description"].astype(str),
                "zone_long_description": zone["Long Description"].astype(str),
            }
        ),
        "dim_commodity": pd.DataFrame(
            {
                "commodity_code": commodity["Numeric Label"].astype(int).astype(str).str.zfill(2),
                "commodity_name": commodity["Description"].astype(str),
            }
        ),
        "dim_mode": pd.DataFrame(
            {
                "mode_code": mode["Numeric Label"].astype(int),
                "mode_name": mode["Description"].astype(str),
            }
        ),
        "dim_trade_type": pd.DataFrame(
            {
                "trade_type_code": trade["Numeric Label"].astype(int),
                "trade_type_name": trade["Description"].astype(str),
            }
        ),
        "dim_year": pd.DataFrame(
            {
                "year": [2024, 2030, 2050],
                "scenario_type": [
                    "Baseline estimate",
                    "Source forecast scenario",
                    "Source forecast scenario",
                ],
            }
        ),
    }
    return {
        name: _write_dimension(frame, settings.processed_dir / f"{name}.parquet")
        for name, frame in dimensions.items()
    }


def build_marts(settings: Settings) -> dict[str, int]:
    """Create BI-sized marts without materializing the enormous row-level long fact."""
    if not settings.source_csv.exists():
        raise FileNotFoundError(f"Missing raw source: {settings.source_csv}")
    settings.processed_dir.mkdir(parents=True, exist_ok=True)
    row_counts = build_dimensions(settings)
    connection = duckdb.connect()
    long_sql = _long_source(settings.source_csv)
    connection.execute(f"CREATE OR REPLACE TEMP TABLE long_flow AS {long_sql}")
    invalid = connection.execute("""
        SELECT COUNT(*) FROM long_flow WHERE origin_zone_code IS NULL
          OR destination_zone_code IS NULL OR commodity_code IS NULL
          OR mode_code IS NULL OR trade_type_code IS NULL
          OR tons_kilotons IS NULL OR value_musd IS NULL OR tmiles_million IS NULL
          OR NOT isfinite(tons_kilotons) OR NOT isfinite(value_musd) OR NOT isfinite(tmiles_million)
          OR tons_kilotons < 0 OR value_musd < 0 OR tmiles_million < 0
    """).fetchone()[0]
    if invalid:
        raise ValueError(
            f"Source has {invalid} invalid year-records. Review instead of silently dropping them."
        )
    connection.execute(
        """
        CREATE OR REPLACE TEMP TABLE valid_flow AS
        SELECT origin_zone_code, destination_zone_code, commodity_code, mode_code,
               trade_type_code, year, scenario_type,
               SUM(tons_kilotons) AS tons_kilotons, SUM(value_musd) AS value_musd,
               SUM(tmiles_million) AS tmiles_million, COUNT(*) AS contributing_source_rows
        FROM long_flow GROUP BY ALL
        """
    )
    dimension_keys = [
        ("origin_zone_code", "dim_zone", "zone_code"),
        ("destination_zone_code", "dim_zone", "zone_code"),
        ("commodity_code", "dim_commodity", "commodity_code"),
        ("mode_code", "dim_mode", "mode_code"),
        ("trade_type_code", "dim_trade_type", "trade_type_code"),
    ]
    for column, table, key in dimension_keys:
        lookup = _csv_path(settings.processed_dir / f"{table}.parquet")
        unknown = connection.execute(f"""SELECT COUNT(*) FROM valid_flow f
            LEFT JOIN read_parquet('{lookup}') d ON f.{column}=d.{key}
            WHERE d.{key} IS NULL""").fetchone()[0]
        if unknown:
            raise ValueError(f"{unknown} records have unknown {column}. Check the source metadata.")
    counts = connection.execute(
        "SELECT (SELECT COUNT(*) FROM long_flow), COUNT(*), SUM(contributing_source_rows) FROM valid_flow"
    ).fetchone()
    settings.quality_dir.mkdir(parents=True, exist_ok=True)
    (settings.quality_dir / "full_transform_checks.json").write_text(
        json.dumps(
            {
                "source_year_records": counts[0],
                "aggregated_fact_rows": counts[1],
                "reconciled_contributing_rows": counts[2],
                "invalid_year_records": invalid,
                "unknown_dimension_codes": 0,
                "fact_grain": "origin, destination, commodity, mode, trade type, year",
                "status": "PASS" if counts[0] == counts[2] else "FAIL",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    outputs = {
        "fact_freight_flow": "SELECT * EXCLUDE (contributing_source_rows) FROM valid_flow",
        "mart_kpi_summary": """
            SELECT year, scenario_type, trade_type_code,
                   SUM(tons_kilotons) AS tons_kilotons,
                   SUM(value_musd) AS value_musd,
                   SUM(tmiles_million) AS tmiles_million,
                   SUM(value_musd) / NULLIF(SUM(tons_kilotons), 0) AS value_density_musd_per_kton,
                   SUM(contributing_source_rows) AS contributing_source_rows
            FROM valid_flow
            GROUP BY year, scenario_type, trade_type_code
            ORDER BY year, trade_type_code
        """,
        "mart_mode_mix": """
            SELECT year, scenario_type, trade_type_code, mode_code,
                   SUM(tons_kilotons) AS tons_kilotons,
                   SUM(value_musd) AS value_musd,
                   SUM(tmiles_million) AS tmiles_million,
                   SUM(tons_kilotons) / NULLIF(SUM(SUM(tons_kilotons)) OVER (PARTITION BY year, trade_type_code), 0) AS mode_share
            FROM valid_flow
            GROUP BY year, scenario_type, trade_type_code, mode_code
            ORDER BY year, trade_type_code, tons_kilotons DESC
        """,
        "mart_commodity_flow": """
            SELECT year, scenario_type, trade_type_code, commodity_code, mode_code,
                   SUM(tons_kilotons) AS tons_kilotons,
                   SUM(value_musd) AS value_musd,
                   SUM(tmiles_million) AS tmiles_million,
                   SUM(value_musd) / NULLIF(SUM(tons_kilotons), 0) AS value_density_musd_per_kton
            FROM valid_flow
            GROUP BY year, scenario_type, trade_type_code, commodity_code, mode_code
            ORDER BY year, tons_kilotons DESC
        """,
        "mart_lane_priority": """
            WITH lane_year AS (
              SELECT year, scenario_type, trade_type_code, origin_zone_code, destination_zone_code, mode_code,
                     SUM(tons_kilotons) AS tons_kilotons,
                     SUM(value_musd) AS value_musd,
                     SUM(tmiles_million) AS tmiles_million
              FROM valid_flow
              GROUP BY year, scenario_type, trade_type_code, origin_zone_code, destination_zone_code, mode_code
            ), wide AS (
              SELECT trade_type_code, origin_zone_code, destination_zone_code, mode_code,
                     MAX(CASE WHEN year = 2024 THEN tons_kilotons END) AS tons_2024_kilotons,
                     MAX(CASE WHEN year = 2030 THEN tons_kilotons END) AS tons_2030_kilotons,
                     MAX(CASE WHEN year = 2050 THEN tons_kilotons END) AS tons_2050_kilotons,
                     MAX(CASE WHEN year = 2024 THEN value_musd END) AS value_2024_musd,
                     MAX(CASE WHEN year = 2024 THEN tmiles_million END) AS tmiles_2024_million
              FROM lane_year
              GROUP BY trade_type_code, origin_zone_code, destination_zone_code, mode_code
            ), scored AS (
              SELECT *,
                POWER(tons_2050_kilotons / NULLIF(tons_2024_kilotons, 0), 1.0 / 26) - 1 AS cagr_2024_2050,
                value_2024_musd / NULLIF(tons_2024_kilotons, 0) AS value_density_2024_musd_per_kton
              FROM wide
            )
            SELECT *,
              PERCENT_RANK() OVER (ORDER BY cagr_2024_2050) *
              PERCENT_RANK() OVER (ORDER BY value_density_2024_musd_per_kton) AS high_growth_lane_index,
              SUM(tons_2024_kilotons) OVER () AS all_lane_tons_2024_kilotons
            FROM scored
            WHERE tons_2024_kilotons > 0 AND tons_2050_kilotons > 0
            ORDER BY high_growth_lane_index DESC
        """,
    }
    for name, query in outputs.items():
        destination = settings.processed_dir / f"{name}.parquet"
        connection.execute(
            f"COPY ({query}) TO '{_csv_path(destination)}' (FORMAT PARQUET, COMPRESSION ZSTD)"
        )
        row_counts[name] = connection.execute(
            f"SELECT COUNT(*) FROM read_parquet('{_csv_path(destination)}')"
        ).fetchone()[0]

    for name in outputs:
        destination = settings.processed_dir / f"{name}.csv"
        parquet = destination.with_suffix(".parquet")
        connection.execute(
            f"COPY (SELECT * FROM read_parquet('{_csv_path(parquet)}')) TO '{_csv_path(destination)}' (HEADER)"
        )
    (settings.processed_dir / "build_manifest.json").write_text(
        json.dumps({"published_marts": row_counts, "source": settings.source_csv.name}, indent=2),
        encoding="utf-8",
    )
    connection.close()
    return row_counts
