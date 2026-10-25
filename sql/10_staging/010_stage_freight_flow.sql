-- Load a UTF-8 export produced by the Python pipeline. Keep the raw FAF CSV immutable.
USE freightflow;

CREATE TABLE IF NOT EXISTS stg_freight_flow (
  origin_zone_code CHAR(3) NOT NULL,
  destination_zone_code CHAR(3) NOT NULL,
  commodity_code CHAR(2) NOT NULL,
  mode_code SMALLINT NOT NULL,
  trade_type_code SMALLINT NOT NULL,
  year SMALLINT NOT NULL,
  scenario_type VARCHAR(30) NOT NULL,
  tons_kilotons DOUBLE NOT NULL,
  value_musd DOUBLE NOT NULL,
  tmiles_million DOUBLE NOT NULL
);

-- Loading is deliberately isolated in 012_load_fact.sql so a large rerun cannot
-- accidentally append to this staging table.  Do not load the raw wide FAF CSV here.
