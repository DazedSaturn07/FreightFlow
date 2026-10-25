USE freightflow;

CREATE OR REPLACE VIEW mart_lane_priority AS
WITH lane_year AS (
  SELECT year, trade_type_code, origin_zone_code, destination_zone_code, mode_code,
         SUM(tons_kilotons) AS tons_kilotons,
         SUM(value_musd) AS value_musd
  FROM fact_freight_flow
  GROUP BY year, trade_type_code, origin_zone_code, destination_zone_code, mode_code
), lanes AS (
  SELECT trade_type_code, origin_zone_code, destination_zone_code, mode_code,
         MAX(CASE WHEN year = 2024 THEN tons_kilotons END) AS tons_2024_kilotons,
         MAX(CASE WHEN year = 2050 THEN tons_kilotons END) AS tons_2050_kilotons,
         MAX(CASE WHEN year = 2024 THEN value_musd END) AS value_2024_musd
  FROM lane_year
  GROUP BY trade_type_code, origin_zone_code, destination_zone_code, mode_code
), scored AS (
  SELECT *,
         POWER(tons_2050_kilotons / NULLIF(tons_2024_kilotons, 0), 1.0 / 26) - 1 AS cagr_2024_2050,
         value_2024_musd / NULLIF(tons_2024_kilotons, 0) AS value_density_2024_musd_per_kton
  FROM lanes
  WHERE tons_2024_kilotons > 0 AND tons_2050_kilotons > 0
), ranked AS (
  SELECT *,
         PERCENT_RANK() OVER (ORDER BY cagr_2024_2050) AS cagr_percentile,
         PERCENT_RANK() OVER (ORDER BY value_density_2024_musd_per_kton) AS density_percentile
  FROM scored
)
SELECT *, cagr_percentile * density_percentile AS high_growth_lane_index
FROM ranked;
