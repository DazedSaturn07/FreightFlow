USE freightflow;

CREATE OR REPLACE VIEW mart_kpi_summary AS
SELECT
  year,
  scenario_type,
  trade_type_code,
  SUM(tons_kilotons) AS tons_kilotons,
  SUM(value_musd) AS value_musd,
  SUM(tmiles_million) AS tmiles_million,
  SUM(value_musd) / NULLIF(SUM(tons_kilotons), 0) AS value_density_musd_per_kton
FROM fact_freight_flow
GROUP BY year, scenario_type, trade_type_code;

CREATE OR REPLACE VIEW mart_mode_mix AS
SELECT
  year,
  scenario_type,
  trade_type_code,
  mode_code,
  SUM(tons_kilotons) AS tons_kilotons,
  SUM(value_musd) AS value_musd,
  SUM(tmiles_million) AS tmiles_million,
  SUM(tons_kilotons) / NULLIF(SUM(SUM(tons_kilotons)) OVER (PARTITION BY year, trade_type_code), 0) AS mode_share
FROM fact_freight_flow
GROUP BY year, scenario_type, trade_type_code, mode_code;
