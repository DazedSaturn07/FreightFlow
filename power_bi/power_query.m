// Parameters ServerParameter and DatabaseParameter stay local to the PBIX.
let
    Source = MySQL.Database(ServerParameter, DatabaseParameter),
    Fact = Source{[Schema="freightflow", Item="fact_freight_flow"]}[Data],
    Selected = Table.SelectColumns(
        Fact,
        {"origin_zone_code", "destination_zone_code", "commodity_code", "mode_code", "trade_type_code", "year", "scenario_type", "tons_kilotons", "value_musd", "tmiles_million"}
    ),
    Typed = Table.TransformColumnTypes(
        Selected,
        {{"year", Int64.Type}, {"tons_kilotons", type number}, {"value_musd", type number}, {"tmiles_million", type number}}
    )
in
    Typed
