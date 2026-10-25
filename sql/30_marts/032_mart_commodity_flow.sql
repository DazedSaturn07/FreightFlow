USE freightflow;
CREATE OR REPLACE VIEW mart_commodity_flow AS
SELECT year, scenario_type, trade_type_code, commodity_code, mode_code,
       SUM(tons_kilotons) AS tons_kilotons, SUM(value_musd) AS value_musd,
       SUM(tmiles_million) AS tmiles_million,
       SUM(value_musd) / NULLIF(SUM(tons_kilotons),0) AS value_density_musd_per_kton
FROM fact_freight_flow
GROUP BY year, scenario_type, trade_type_code, commodity_code, mode_code;

CREATE OR REPLACE VIEW dim_origin_zone AS SELECT * FROM dim_zone;
CREATE OR REPLACE VIEW dim_destination_zone AS SELECT * FROM dim_zone;
