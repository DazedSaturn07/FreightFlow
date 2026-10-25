"""Run one FreightFlow stage at a time, or all three after learning the workflow."""

import argparse
import json

from freightflow.analysis import reconcile, write_findings
from freightflow.config import settings
from freightflow.quality import profile_csv, save_profile, write_manifest
from freightflow.transform import build_marts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["profile", "transform", "analyze", "all"])
    command = parser.parse_args().command
    config = settings()
    if command in ["profile", "all"]:
        report = profile_csv(config.source_csv)
        write_manifest(
            config.source_csv, config.quality_dir / "source_manifest.json", report.row_count
        )
        save_profile(report, config.quality_dir / "data_quality_report.json")
        print(
            json.dumps(
                {
                    "rows": report.row_count,
                    "columns": report.column_count,
                    "duplicate_sample_keys": report.duplicate_sample_keys,
                }
            )
        )
    if command in ["transform", "all"]:
        print(json.dumps(build_marts(config), indent=2))
    if command in ["analyze", "all"]:
        print(reconcile(config))
        print(write_findings(config))


if __name__ == "__main__":
    main()
