"""Prepare compact, named Excel tables from the checked analytical outputs."""

import json
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/processed"


def main():
    con = duckdb.connect()
    for file in DATA.glob("*.parquet"):
        con.execute(f"CREATE VIEW {file.stem} AS SELECT * FROM read_parquet('{file.as_posix()}')")
    queries = {
        "kpi": "SELECT k.year,split_part(t.trade_type_name, ' ', 1),k.tons_kilotons,k.value_musd,k.tmiles_million FROM mart_kpi_summary k JOIN dim_trade_type t USING(trade_type_code) ORDER BY 1,2",
        "modes": "SELECT m.year,split_part(t.trade_type_name, ' ', 1),d.mode_name,m.tons_kilotons,m.value_musd,m.tmiles_million FROM mart_mode_mix m JOIN dim_trade_type t USING(trade_type_code) JOIN dim_mode d USING(mode_code) ORDER BY 1,2,3",
        "commodities": "SELECT c.year,split_part(t.trade_type_name, ' ', 1),d.commodity_name,SUM(c.tons_kilotons) tons_kilotons FROM mart_commodity_flow c JOIN dim_trade_type t USING(trade_type_code) JOIN dim_commodity d USING(commodity_code) GROUP BY ALL ORDER BY 1,2,4 DESC",
        "lanes": "SELECT split_part(t.trade_type_name, ' ', 1),o.zone_name origin,d.zone_name destination,m.mode_name,l.tons_2024_kilotons,l.tons_2050_kilotons,l.cagr_2024_2050,l.value_density_2024_musd_per_kton,l.high_growth_lane_index FROM mart_lane_priority l JOIN dim_trade_type t USING(trade_type_code) JOIN dim_zone o ON o.zone_code=l.origin_zone_code JOIN dim_zone d ON d.zone_code=l.destination_zone_code JOIN dim_mode m USING(mode_code) WHERE l.tons_2024_kilotons>=1000 AND l.mode_code BETWEEN 1 AND 6 ORDER BY high_growth_lane_index DESC,origin_zone_code,destination_zone_code,mode_code,trade_type_code LIMIT 250",
    }
    payload = {}
    for name, query in queries.items():
        frame = con.execute(query).df()
        payload[name] = [frame.columns.tolist()] + frame.values.tolist()
        if name == "lanes":
            frame.to_csv(ROOT / "artifacts/exports/lane_candidates.csv", index=False)
    frame = pd.read_csv(ROOT / "artifacts/quality/reconciliation.csv")
    payload["reconciliation"] = [frame.columns.tolist()] + frame.values.tolist()
    (DATA / "excel_inputs.json").write_text(json.dumps(payload, allow_nan=False), encoding="utf-8")
    con.close()
    print("Prepared Excel inputs: " + ", ".join(f"{k}={len(v) - 1}" for k, v in payload.items()))


if __name__ == "__main__":
    main()
