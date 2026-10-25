-- Promote the validated staging rows after dimensions have loaded.
-- This project owns the complete fact table, so replace it atomically from staging
-- to prevent stale rows when the same generated source is reloaded.
USE freightflow;

START TRANSACTION;
DELETE FROM fact_freight_flow;

INSERT INTO fact_freight_flow (
  origin_zone_code, destination_zone_code, commodity_code, mode_code,
  trade_type_code, year, scenario_type, tons_kilotons, value_musd, tmiles_million
)
SELECT
  origin_zone_code, destination_zone_code, commodity_code, mode_code,
  trade_type_code, year, scenario_type, tons_kilotons, value_musd, tmiles_million
FROM stg_freight_flow
ORDER BY origin_zone_code, destination_zone_code, commodity_code, mode_code, trade_type_code, year
;

COMMIT;
