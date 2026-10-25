"""Run the numbered MySQL sections and compare database totals with Python.

The password is prompted without echo, or read from FREIGHTFLOW_MYSQL_PASSWORD.
Only the freightflow schema is modified. Run transform and analyze first.
"""

import argparse
import csv
import getpass
import json
import math
import os
import re
from itertools import islice
from pathlib import Path

import pymysql

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=3306)
    parser.add_argument("--user", default="root")
    parser.add_argument(
        "--start-at",
        choices=["00", "20", "30"],
        default="00",
        help="Resume from an already loaded staging table (20) or validate completed facts (30).",
    )
    args = parser.parse_args()
    password = os.getenv("FREIGHTFLOW_MYSQL_PASSWORD") or getpass.getpass("MySQL password: ")
    connection = pymysql.connect(
        host=args.host,
        port=args.port,
        user=args.user,
        password=password,
        local_infile=True,
        autocommit=True,
        charset="utf8mb4",
        read_timeout=7200,
        write_timeout=1800,
    )
    quality = ROOT / "artifacts/quality"
    quality.mkdir(parents=True, exist_ok=True)
    with connection, connection.cursor() as cursor:
        cursor.execute("SELECT VERSION(), @@local_infile")
        version, local_infile = cursor.fetchone()
        print(f"MySQL {version}; LOCAL INFILE={local_infile}", flush=True)
        if not local_infile:
            print("Using parameterized batch inserts because LOCAL INFILE is disabled.", flush=True)
        if args.start_at == "20":
            cursor.execute("SELECT COUNT(*) FROM freightflow.stg_freight_flow")
            with (ROOT / "data/processed/build_manifest.json").open() as handle:

                expected = json.load(handle)["published_marts"]["fact_freight_flow"]
            if cursor.fetchone()[0] != expected:
                raise RuntimeError("Staging is incomplete. Rerun the normal load before resuming.")
        for path in sorted((ROOT / "sql").glob("*/*.sql")):
            if path.parent.name[:2] < args.start_at:
                continue
            text = path.read_text(encoding="utf-8")
            text = "\n".join(
                line for line in text.splitlines() if not line.lstrip().startswith("--")
            )
            text = text.replace("<ABSOLUTE_PATH>", (ROOT / "data/processed").as_posix())
            print(f"Running {path.relative_to(ROOT)}", flush=True)
            for statement_number, statement in enumerate(text.split(";")):
                if not statement.strip():
                    continue
                if not local_infile and statement.lstrip().upper().startswith("LOAD DATA"):
                    table = re.search(r"INTO TABLE (\w+)", statement, re.I)[1]
                    source = (
                        ROOT
                        / "data/processed"
                        / (
                            "fact_freight_flow.csv"
                            if table == "stg_freight_flow"
                            else f"{table}.csv"
                        )
                    )
                    cursor.execute(f"SHOW COLUMNS FROM {table}")
                    target_columns = {r[0] for r in cursor.fetchall()}
                    with source.open(newline="", encoding="utf-8") as handle:
                        reader = csv.DictReader(handle)
                        columns = [name for name in reader.fieldnames if name in target_columns]
                        names = ",".join(f"`{name}`" for name in columns)
                        placeholders = ",".join(["%s"] * len(columns))
                        command = f"INSERT INTO {table} ({names}) VALUES ({placeholders})"
                        if table.startswith("dim_"):
                            command += " ON DUPLICATE KEY UPDATE " + ",".join(
                                f"`{name}`=VALUES(`{name}`)" for name in columns[1:]
                            )
                        count = 0
                        while batch := list(islice(reader, 10000)):
                            cursor.executemany(
                                command, [[row[name] for name in columns] for row in batch]
                            )
                            count += len(batch)
                            if count % 500000 == 0:
                                print(f"  {table}: {count:,} rows loaded", flush=True)
                    continue
                cursor.execute(statement)
                if statement.lstrip().upper().startswith("LOAD DATA") and cursor.warning_count:
                    cursor.execute("SHOW WARNINGS LIMIT 5")
                    raise RuntimeError(f"CSV load warnings: {cursor.fetchall()}")
                if cursor.description:
                    result = cursor.fetchall()
                    if [col[0] for col in cursor.description] == ["check_name", "failures"]:
                        if any(row[1] != 0 for row in result):
                            raise RuntimeError(f"Database quality checks failed: {result}")
                    with (quality / f"{path.stem}_{statement_number}.csv").open(
                        "w", newline="", encoding="utf-8"
                    ) as handle:
                        writer = csv.writer(handle)
                        writer.writerow([col[0] for col in cursor.description])
                        writer.writerows(result)
        cursor.execute(
            "SELECT year,trade_type_code,tons_kilotons,value_musd,tmiles_million FROM mart_kpi_summary ORDER BY year,trade_type_code"
        )
        actual = {(r[0], r[1]): r[2:] for r in cursor.fetchall()}
        rows = []
        with (ROOT / "data/processed/mart_kpi_summary.csv").open(
            newline="", encoding="utf-8"
        ) as handle:
            for row in csv.DictReader(handle):
                key = (int(row["year"]), int(row["trade_type_code"]))
                for i, metric in enumerate(["tons_kilotons", "value_musd", "tmiles_million"]):
                    expected, found = float(row[metric]), float(actual[key][i])
                    passed = math.isclose(expected, found, rel_tol=1e-10, abs_tol=1e-6)
                    rows.append(
                        [
                            *key,
                            metric,
                            expected,
                            found,
                            found - expected,
                            "PASS" if passed else "FAIL",
                        ]
                    )
        with (quality / "mysql_reconciliation.csv").open(
            "w", newline="", encoding="utf-8"
        ) as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "year",
                    "trade_type_code",
                    "metric",
                    "python_value",
                    "mysql_value",
                    "difference",
                    "status",
                ]
            )
            writer.writerows(rows)
        cursor.execute("SELECT COUNT(*) FROM fact_freight_flow")
        print(
            f"Fact rows: {cursor.fetchone()[0]:,}; reconciled {len(rows)} KPI comparisons.",
            flush=True,
        )
        if len(actual) != 9 or any(row[-1] != "PASS" for row in rows):
            raise RuntimeError(
                "Database totals differ from Python; inspect mysql_reconciliation.csv"
            )
        print("PASS: MySQL totals agree with Python.", flush=True)


if __name__ == "__main__":
    main()
