-- Replace the placeholder with the generated fact_freight_flow.csv path.
-- First run `python -m freightflow.cli transform`.  The CSV is intentionally
-- excluded from Git because it is a large reproducible derivative.
USE freightflow;

TRUNCATE TABLE stg_freight_flow;

LOAD DATA LOCAL INFILE '<ABSOLUTE_PATH>/fact_freight_flow.csv'
INTO TABLE stg_freight_flow
CHARACTER SET utf8mb4
FIELDS TERMINATED BY ',' ENCLOSED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 LINES;
