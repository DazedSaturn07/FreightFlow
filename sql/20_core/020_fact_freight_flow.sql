USE freightflow;

CREATE TABLE IF NOT EXISTS fact_freight_flow (
  origin_zone_code CHAR(3) NOT NULL,
  destination_zone_code CHAR(3) NOT NULL,
  commodity_code CHAR(2) NOT NULL,
  mode_code SMALLINT NOT NULL,
  trade_type_code SMALLINT NOT NULL,
  year SMALLINT NOT NULL,
  scenario_type VARCHAR(30) NOT NULL,
  tons_kilotons DOUBLE NOT NULL,
  value_musd DOUBLE NOT NULL,
  tmiles_million DOUBLE NOT NULL,
  PRIMARY KEY (origin_zone_code, destination_zone_code, commodity_code, mode_code, trade_type_code, year),
  INDEX idx_fact_year_trade_mode (year, trade_type_code, mode_code),
  INDEX idx_fact_lane_year (origin_zone_code, destination_zone_code, year),
  CONSTRAINT fk_fact_origin FOREIGN KEY (origin_zone_code) REFERENCES dim_zone(zone_code),
  CONSTRAINT fk_fact_destination FOREIGN KEY (destination_zone_code) REFERENCES dim_zone(zone_code),
  CONSTRAINT fk_fact_commodity FOREIGN KEY (commodity_code) REFERENCES dim_commodity(commodity_code),
  CONSTRAINT fk_fact_mode FOREIGN KEY (mode_code) REFERENCES dim_mode(mode_code),
  CONSTRAINT fk_fact_trade_type FOREIGN KEY (trade_type_code) REFERENCES dim_trade_type(trade_type_code),
  CONSTRAINT fk_fact_year FOREIGN KEY (year) REFERENCES dim_year(year)
);

