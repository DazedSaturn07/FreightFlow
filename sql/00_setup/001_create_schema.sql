-- FreightFlow target schema for MySQL 8.0+. Run after creating a least-privilege user.
CREATE DATABASE IF NOT EXISTS freightflow
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_0900_ai_ci;
USE freightflow;

CREATE TABLE IF NOT EXISTS dim_zone (
  zone_code CHAR(3) NOT NULL,
  zone_name VARCHAR(255) NOT NULL,
  zone_type VARCHAR(20) NOT NULL DEFAULT 'Domestic',
  PRIMARY KEY (zone_code)
);

CREATE TABLE IF NOT EXISTS dim_commodity (
  commodity_code CHAR(2) NOT NULL,
  commodity_name VARCHAR(255) NOT NULL,
  PRIMARY KEY (commodity_code)
);

CREATE TABLE IF NOT EXISTS dim_mode (
  mode_code SMALLINT NOT NULL,
  mode_name VARCHAR(100) NOT NULL,
  PRIMARY KEY (mode_code)
);

CREATE TABLE IF NOT EXISTS dim_trade_type (
  trade_type_code SMALLINT NOT NULL,
  trade_type_name VARCHAR(100) NOT NULL,
  PRIMARY KEY (trade_type_code)
);

CREATE TABLE IF NOT EXISTS dim_year (
  year SMALLINT NOT NULL,
  scenario_type VARCHAR(30) NOT NULL,
  PRIMARY KEY (year)
);
