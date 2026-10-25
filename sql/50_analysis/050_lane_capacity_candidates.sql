USE freightflow;

SELECT *
FROM mart_lane_priority
WHERE tons_2024_kilotons >= 1000
  AND mode_code BETWEEN 1 AND 6
ORDER BY high_growth_lane_index DESC
LIMIT 50;
