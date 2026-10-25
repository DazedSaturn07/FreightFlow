USE freightflow;

SELECT 'missing_origin' AS check_name, COUNT(*) AS failures
FROM fact_freight_flow f LEFT JOIN dim_zone d ON f.origin_zone_code=d.zone_code WHERE d.zone_code IS NULL
UNION ALL
SELECT 'missing_destination',COUNT(*) FROM fact_freight_flow f LEFT JOIN dim_zone d ON f.destination_zone_code=d.zone_code WHERE d.zone_code IS NULL
UNION ALL
SELECT 'missing_commodity',COUNT(*) FROM fact_freight_flow f LEFT JOIN dim_commodity d USING(commodity_code) WHERE d.commodity_code IS NULL
UNION ALL
SELECT 'missing_mode',COUNT(*) FROM fact_freight_flow f LEFT JOIN dim_mode d USING(mode_code) WHERE d.mode_code IS NULL
UNION ALL
SELECT 'missing_trade',COUNT(*) FROM fact_freight_flow f LEFT JOIN dim_trade_type d USING(trade_type_code) WHERE d.trade_type_code IS NULL
UNION ALL
SELECT 'missing_year',COUNT(*) FROM fact_freight_flow f LEFT JOIN dim_year d USING(year) WHERE d.year IS NULL
UNION ALL
SELECT 'negative_metrics',COUNT(*) FROM fact_freight_flow WHERE tons_kilotons<0 OR value_musd<0 OR tmiles_million<0
UNION ALL
SELECT 'staging_fact_count_difference',ABS((SELECT COUNT(*) FROM stg_freight_flow)-(SELECT COUNT(*) FROM fact_freight_flow));

SELECT * FROM mart_kpi_summary ORDER BY year,trade_type_code;
