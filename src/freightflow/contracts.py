"""Source and metric contracts kept independent from transformation code."""

from __future__ import annotations

IDENTITY_COLUMNS = (
    "fr_orig",
    "dms_orig",
    "dms_dest",
    "fr_dest",
    "fr_inmode",
    "dms_mode",
    "fr_outmode",
    "sctg2",
    "trade_type",
    "dist_band",
)

REQUIRED_COLUMNS = IDENTITY_COLUMNS + (
    "tons_2024",
    "tons_2030",
    "tons_2050",
    "value_2024",
    "value_2030",
    "value_2050",
    "tmiles_2024",
    "tmiles_2030",
    "tmiles_2050",
)

YEARS = (2024, 2030, 2050)
BASELINE_YEAR = 2024
