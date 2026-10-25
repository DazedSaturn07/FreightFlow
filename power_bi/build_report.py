"""Create the native Power BI project. Business calculations stay in measures.dax.

Report JSON describes layout, not additional analysis. Regenerate after moving folders.
"""

import argparse
import json
import re
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/"
NAVY, BLUE, RUST, PAPER, GRAY = "#183349", "#466D86", "#A76542", "#F3F4F2", "#667581"
PAGES = [
    ("overview", "Freight network"),
    ("lanes", "Lane priorities"),
    ("modes", "Mode mix"),
    ("commodities", "Commodity flows"),
    ("scenarios", "Growth scenarios"),
]


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def literal(value):
    if isinstance(value, bool):
        value = str(value).lower()
    elif isinstance(value, int):
        value = f"{value}L"
    else:
        value = "'" + str(value).replace("'", "''") + "'"
    return {"expr": {"Literal": {"Value": value}}}


def color(value):
    return {"solid": {"color": literal(value)}}


def props(**values):
    return [{"properties": values}]


def field(table, column, measure=False):
    return {
        "Measure" if measure else "Column": {
            "Expression": {"SourceRef": {"Entity": table}},
            "Property": column,
        }
    }


def projection(table, column, measure=False, label=None):
    return {
        "field": field(table, column, measure),
        "queryRef": f"{table}.{column}",
        "displayName": label or column.replace("_", " ").title(),
    }


def equal(table, column, value, measure=False):
    expression = field(table, column, measure)
    left = json.loads(json.dumps(expression))
    left["Measure" if measure else "Column"]["Expression"]["SourceRef"] = {"Source": "f"}
    return {
        "name": re.sub(r"\W", "_", column),
        "field": expression,
        "type": "Advanced",
        "howCreated": "User",
        "filter": {
            "Version": 2,
            "From": [{"Name": "f", "Entity": table, "Type": 0}],
            "Where": [
                {
                    "Condition": {
                        "Comparison": {
                            "ComparisonKind": 0,
                            "Left": left,
                            "Right": literal(value)["expr"],
                        }
                    }
                }
            ],
        },
    }


def model(folder):
    tables = []
    names = [
        "fact_freight_flow",
        "mart_lane_priority",
        "dim_origin_zone",
        "dim_destination_zone",
        "dim_mode",
        "dim_commodity",
        "dim_trade_type",
        "dim_year",
        "dim_lane",
    ]
    for name in names:
        frame = pd.read_csv(
            folder / f"{name}.csv",
            nrows=200,
            dtype={
                c: str
                for c in [
                    "zone_code",
                    "commodity_code",
                    "origin_zone_code",
                    "destination_zone_code",
                ]
            },
        )
        columns, types = [], []
        for col in frame:
            is_text = (
                col.endswith("_code")
                and col not in ["mode_code", "trade_type_code"]
                or "name" in col
                or col in ["scenario_type", "zone_long_description", "lane_key"]
            )
            dtype, mtype = (
                ("string", "type text")
                if is_text
                else (
                    ("int64", "Int64.Type")
                    if col in ["year", "mode_code", "trade_type_code"]
                    else ("double", "type number")
                )
            )
            columns.append(
                {"name": col, "dataType": dtype, "sourceColumn": col, "summarizeBy": "none"}
            )
            types.append('{"' + col + '", ' + mtype + "}")
        expression = [
            "let",
            f' Source = Csv.Document(File.Contents(DataFolder & "/{name}.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),',
            " Headers = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),",
            " Typed = Table.TransformColumnTypes(Headers, {" + ", ".join(types) + '}, "en-US")',
        ]
        if name in ["fact_freight_flow", "mart_lane_priority"]:
            expression[-1] += ","
            expression += [
                ' AddLane = Table.AddColumn(Typed, "lane_key", each [origin_zone_code] & "|" & [destination_zone_code] & "|" & Text.From([mode_code]), type text)',
                "in",
                " AddLane",
            ]
            columns.append(
                {
                    "name": "lane_key",
                    "dataType": "string",
                    "sourceColumn": "lane_key",
                    "summarizeBy": "none",
                }
            )
        else:
            expression += ["in", " Typed"]
        tables.append(
            {
                "name": name,
                "columns": columns,
                "partitions": [
                    {
                        "name": name,
                        "mode": "import",
                        "source": {"type": "m", "expression": expression},
                    }
                ],
            }
        )
    dax = (ROOT / "power_bi/measures.dax").read_text(encoding="utf-8")
    dax = re.sub(r"--[^\n]*", "", dax)
    matches = list(re.finditer(r"^([^\n=]+)\s*=\s*\n", dax, re.M))
    measures = []
    for i, match in enumerate(matches):
        name = match.group(1).strip()
        body = dax[
            match.end() : matches[i + 1].start() if i + 1 < len(matches) else len(dax)
        ].strip()
        if "billion" in name or name.endswith("($T)") or name.endswith("(T)"):
            fmt = "0.00"
        elif "Density" in name:
            fmt = "0.000"
        elif "Index" in name:
            fmt = "0.000"
        elif "Count" in name:
            fmt = "#,##0"
        elif any(x in name for x in ["Share", "Concentration", "CAGR", "Growth"]):
            fmt = "0.0%"
        else:
            fmt = "#,##0.0"
        measures.append(
            {
                "name": name,
                "expression": body,
                "formatString": fmt,
                "displayFolder": "Freight metrics",
            }
        )
    tables[0]["measures"] = measures
    relationships = []
    dimensions = [
        ("dim_origin_zone", "zone_code", "origin_zone_code"),
        ("dim_destination_zone", "zone_code", "destination_zone_code"),
        ("dim_mode", "mode_code", "mode_code"),
        ("dim_trade_type", "trade_type_code", "trade_type_code"),
        ("dim_lane", "lane_key", "lane_key"),
    ]
    for fact in ["fact_freight_flow", "mart_lane_priority"]:
        for dim, key, col in dimensions:
            relationships.append(
                {
                    "name": fact + "_" + dim,
                    "fromTable": fact,
                    "fromColumn": col,
                    "toTable": dim,
                    "toColumn": key,
                    "crossFilteringBehavior": "oneDirection",
                }
            )
    for dim, key in [("dim_year", "year"), ("dim_commodity", "commodity_code")]:
        relationships.append(
            {
                "name": "flow_" + dim,
                "fromTable": "fact_freight_flow",
                "fromColumn": key,
                "toTable": dim,
                "toColumn": key,
                "crossFilteringBehavior": "oneDirection",
            }
        )
    return {
        "compatibilityLevel": 1606,
        "model": {
            "culture": "en-US",
            "sourceQueryCulture": "en-US",
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "annotations": [{"name": "__PBI_TimeIntelligenceEnabled", "value": "0"}],
            "expressions": [
                {
                    "name": "DataFolder",
                    "kind": "m",
                    "expression": json.dumps(folder.as_posix())
                    + ' meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]',
                }
            ],
            "tables": tables,
            "relationships": relationships,
        },
    }


def prepare(folder):
    # Role-playing zone dimensions prevent ambiguous origin/destination filtering.
    zone = pd.read_csv(folder / "dim_zone.csv", dtype={"zone_code": str})
    for name in ["dim_origin_zone", "dim_destination_zone"]:
        zone.to_csv(folder / f"{name}.csv", index=False)
    con = duckdb.connect()
    query = f"""SELECT DISTINCT f.origin_zone_code||'|'||f.destination_zone_code||'|'||f.mode_code::VARCHAR lane_key,
      o.zone_name||' to '||d.zone_name||' ('||m.mode_name||')' lane_name
      FROM read_parquet('{(folder / "fact_freight_flow.parquet").as_posix()}') f
      JOIN read_csv('{(folder / "dim_zone.csv").as_posix()}',all_varchar=true) o ON o.zone_code=f.origin_zone_code
      JOIN read_csv('{(folder / "dim_zone.csv").as_posix()}',all_varchar=true) d ON d.zone_code=f.destination_zone_code
      JOIN read_csv('{(folder / "dim_mode.csv").as_posix()}') m USING(mode_code)"""
    con.execute(f"COPY ({query}) TO '{(folder / 'dim_lane.csv').as_posix()}' (HEADER)")
    con.close()
    trade = pd.read_csv(folder / "dim_trade_type.csv")
    trade["trade_type_name"] = trade.trade_type_name.str.split().str[0]
    # The source-owned long labels remain in dim_trade_type.csv; the model uses friendly labels.
    trade.to_csv(folder / "bi_trade_type.csv", index=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-folder", type=Path, default=ROOT / "data/processed")
    args = parser.parse_args()
    folder = args.data_folder.resolve()
    prepare(folder)
    out = ROOT / "power_bi"
    report = out / "FreightFlow.Report"
    definition = report / "definition"
    save(
        out / "FreightFlow.pbip",
        {
            "version": "1.0",
            "artifacts": [{"report": {"path": "FreightFlow.Report"}}],
            "settings": {"enableAutoRecovery": True},
        },
    )
    save(
        report / "definition.pbir",
        {
            "version": "4.0",
            "datasetReference": {"byPath": {"path": "../FreightFlow.SemanticModel"}},
        },
    )
    save(out / "FreightFlow.SemanticModel/definition.pbism", {"version": "4.2", "settings": {}})
    semantic = model(folder)
    for table in semantic["model"]["tables"]:
        if table["name"] == "dim_trade_type":
            table["partitions"][0]["source"]["expression"][1] = table["partitions"][0]["source"][
                "expression"
            ][1].replace("/dim_trade_type.csv", "/bi_trade_type.csv")
    save(out / "FreightFlow.SemanticModel/model.bim", semantic)
    save(
        definition / "version.json",
        {"$schema": SCHEMA + "versionMetadata/1.0.0/schema.json", "version": "2.0.0"},
    )
    theme = {
        "name": "FreightFlow",
        "dataColors": [BLUE, RUST, "#8F9C89", "#9DB0BA", "#D5B798"],
        "background": "#FFFFFF",
        "foreground": NAVY,
        "tableAccent": BLUE,
        "textClasses": {
            "title": {"fontFace": "Segoe UI", "fontSize": 13, "color": NAVY},
            "label": {"fontFace": "Segoe UI", "fontSize": 11, "color": NAVY},
            "callout": {"fontFace": "Segoe UI", "fontSize": 26, "color": BLUE},
        },
    }
    save(out / "theme.json", theme)
    save(report / "StaticResources/RegisteredResources/FreightFlow.json", theme)
    versions = {"visual": "1.8.89", "page": "1.3.89", "report": "2.0.89"}
    save(
        definition / "report.json",
        {
            "$schema": SCHEMA + "report/3.3.0/schema.json",
            "themeCollection": {
                "baseTheme": {
                    "name": "CY24SU02",
                    "reportVersionAtImport": versions,
                    "type": "SharedResources",
                },
                "customTheme": {
                    "name": "FreightFlow.json",
                    "reportVersionAtImport": versions,
                    "type": "RegisteredResources",
                },
            },
            "resourcePackages": [
                {
                    "name": "SharedResources",
                    "type": "SharedResources",
                    "items": [
                        {
                            "name": "CY24SU02",
                            "path": "BaseThemes/CY24SU02.json",
                            "type": "BaseTheme",
                        }
                    ],
                },
                {
                    "name": "RegisteredResources",
                    "type": "RegisteredResources",
                    "items": [
                        {
                            "name": "FreightFlow.json",
                            "path": "FreightFlow.json",
                            "type": "CustomTheme",
                        }
                    ],
                },
            ],
            "settings": {
                "useStylableVisualContainerHeader": True,
                "exportDataMode": "AllowSummarized",
                "defaultDrillFilterOtherVisuals": True,
            },
            "objects": {"outspacePane": props(expanded=literal(False))},
        },
    )
    save(
        definition / "pages/pages.json",
        {
            "$schema": SCHEMA + "pagesMetadata/1.0.0/schema.json",
            "pageOrder": [p[0] for p in PAGES],
            "activePageName": "overview",
        },
    )
    for page, page_title in PAGES:
        page_dir = definition / "pages" / page
        page_json = {
            "$schema": SCHEMA + "page/2.1.0/schema.json",
            "name": page,
            "displayName": page_title,
            "displayOption": "FitToPage",
            "width": 1440,
            "height": 900,
            "objects": {"background": props(color=color(PAPER), transparency=literal(0))},
        }
        if page not in ["scenarios", "lanes"]:
            page_json["filterConfig"] = {"filters": [equal("dim_year", "year", 2024)]}
        save(page_dir / "page.json", page_json)
        visuals = []
        mobile_y = 8

        def visual(name, kind, x, y, w, h, title="", query=None, objects=None, filters=None):
            nonlocal mobile_y
            name = page + "_" + name
            z = len(visuals)
            vc = {
                "background": props(
                    show=literal(True), color=color("#FFFFFF"), transparency=literal(0)
                ),
                "border": props(show=literal(False)),
                "general": props(altText=literal(title or name)),
            }
            if title:
                vc["title"] = props(
                    show=literal(True),
                    text=literal(title),
                    fontSize=literal(12),
                    bold=literal(True),
                    fontColor=color(NAVY),
                    titleWrap=literal(True),
                )
            v = {
                "$schema": SCHEMA + "visualContainer/2.4.0/schema.json",
                "name": name,
                "position": {"x": x, "y": y, "z": z, "width": w, "height": h, "tabOrder": z},
                "visual": {
                    "visualType": kind,
                    "visualContainerObjects": vc,
                    "objects": objects or {},
                    "drillFilterOtherVisuals": True,
                },
            }
            if query:
                v["visual"]["query"] = query
            if filters:
                v["filterConfig"] = {"filters": filters}
            dest = page_dir / "visuals" / name
            save(dest / "visual.json", v)
            if kind != "actionButton" and not any(
                name.endswith("_" + n) for n in ["brand", "edition", "scope", "footer"]
            ):
                if name.endswith("_title"):
                    mh = 60
                elif name.endswith("_period"):
                    mh = 65
                elif kind == "textbox":
                    mh = 180
                else:
                    mh = 80 if kind == "slicer" else (100 if kind == "cardVisual" else 300)
                save(
                    dest / "mobile.json",
                    {
                        "$schema": SCHEMA + "visualContainerMobileState/1.0.0/schema.json",
                        "position": {"x": 8, "y": mobile_y, "z": z, "width": 304, "height": mh},
                    },
                )
                mobile_y += mh + 8
            visuals.append(v)
            return v

        def text(name, value, x, y, w, h, size=12, ink=GRAY):
            return visual(
                name,
                "textbox",
                x,
                y,
                w,
                h,
                objects={
                    "general": props(
                        paragraphs=[
                            {
                                "textRuns": [
                                    {
                                        "value": value,
                                        "textStyle": {
                                            "fontFamily": "Segoe UI",
                                            "fontSize": f"{size}pt",
                                            "color": ink,
                                        },
                                    }
                                ]
                            }
                        ]
                    )
                },
            )

        def metric(name, measure, label, x):
            return visual(
                name,
                "cardVisual",
                x,
                200,
                280,
                105,
                label,
                {
                    "queryState": {
                        "Data": {
                            "projections": [projection("fact_freight_flow", measure, True, label)]
                        }
                    }
                },
                {
                    "value": [
                        {
                            "selector": {"id": "default"},
                            "properties": {
                                "fontSize": literal(27),
                                "fontColor": color(BLUE),
                                "labelDisplayUnits": literal(1),
                            },
                        }
                    ],
                    "label": [
                        {"selector": {"id": "default"}, "properties": {"show": literal(False)}}
                    ],
                    "outline": [
                        {"selector": {"id": "default"}, "properties": {"show": literal(False)}}
                    ],
                },
            )

        def slicer(name, table, column, label, x, width=280):
            return visual(
                "control_" + name,
                "slicer",
                x,
                110,
                width,
                72,
                label,
                {
                    "queryState": {
                        "Values": {"projections": [projection(table, column, label=label)]}
                    }
                },
                {
                    "data": props(mode=literal("Dropdown")),
                    "header": props(show=literal(False)),
                    "selection": props(
                        singleSelect=literal(False), selectAllCheckboxEnabled=literal(True)
                    ),
                    "general": props(selfFilterEnabled=literal(True)),
                },
            )

        def chart(name, kind, table, column, measure, title, x, y, w, h):
            query = {
                "queryState": {
                    "Category": {"projections": [projection(table, column)]},
                    "Y": {"projections": [projection("fact_freight_flow", measure, True)]},
                },
                "sortDefinition": {
                    "sort": [
                        {
                            "field": field(table, column)
                            if kind == "lineChart"
                            else field("fact_freight_flow", measure, True),
                            "direction": "Ascending" if kind == "lineChart" else "Descending",
                        }
                    ]
                },
            }
            return visual(
                name,
                kind,
                x,
                y,
                w,
                h,
                title,
                query,
                {
                    "categoryAxis": props(fontSize=literal(10), showAxisTitle=literal(False)),
                    "valueAxis": props(fontSize=literal(10), showAxisTitle=literal(False)),
                    "legend": props(show=literal(False)),
                    "general": props(responsive=literal(True)),
                    "dataPoint": props(defaultColor=color(BLUE)),
                },
            )

        def table(name, projections, title, x, y, w, h, filters=None):
            query = {"queryState": {"Values": {"projections": projections}}}
            if name in ["candidates", "density", "shares"]:
                measure = "High Growth Lane Index" if name == "candidates" else "Tonnage (ktons)"
                query["sortDefinition"] = {
                    "sort": [
                        {
                            "field": field("fact_freight_flow", measure, True),
                            "direction": "Descending",
                        }
                    ]
                }
            return visual(
                name,
                "tableEx",
                x,
                y,
                w,
                h,
                title,
                query,
                {
                    "columnHeaders": props(
                        fontSize=literal(11), fontColor=color(NAVY), wordWrap=literal(True)
                    ),
                    "values": props(fontSize=literal(10), wordWrap=literal(False)),
                    "grid": props(gridVertical=literal(False)),
                    "total": props(totals=literal(False)),
                },
                filters,
            )

        text("brand", "FREIGHTFLOW", 24, 15, 185, 55, 18, NAVY)
        text("edition", "U.S. FREIGHT\nNETWORK REVIEW", 24, 80, 172, 65, 10)
        text("title", page_title, 230, 10, 1178, 65, 26, NAVY)
        text(
            "period",
            "FAF5.7.1  /  "
            + (
                "2024 estimate and 2030-2050 source forecasts"
                if page in ["scenarios", "lanes"]
                else "2024 baseline estimate"
            )
            + "  /  value in 2017 USD",
            230,
            72,
            1178,
            30,
            11,
        )
        for i, (destination, label) in enumerate(PAGES):
            v = visual(
                "nav_" + destination,
                "actionButton",
                24,
                190 + i * 58,
                172,
                48,
                objects={
                    "text": [
                        {"properties": {"show": literal(True)}},
                        {
                            "selector": {"id": "default"},
                            "properties": {
                                "text": literal(f"{i + 1:02}  {label}"),
                                "fontColor": color(NAVY),
                                "fontSize": literal(10),
                                "horizontalAlignment": literal("left"),
                            },
                        },
                    ],
                    "fill": [
                        {"properties": {"show": literal(True)}},
                        {
                            "selector": {"id": "default"},
                            "properties": {
                                "fillColor": color("#DCE5E8" if page == destination else PAPER)
                            },
                        },
                    ],
                    "shape": props(tileShape=literal("rectangle")),
                    "icon": props(show=literal(False)),
                    "outline": props(show=literal(False)),
                },
            )
            v["visual"]["visualContainerObjects"]["visualLink"] = props(
                show=literal(True),
                type=literal("PageNavigation"),
                navigationSection=literal(destination),
            )
            save(page_dir / "visuals" / v["name"] / "visual.json", v)
        text(
            "scope",
            "SOURCE\nFreight Analysis\nFramework 5.7.1\n\nUNITS\nktons: thousand tons\n$M: million 2017 USD\nTon-miles: millions\n\nCapacity and cost\nare not in this source.",
            24,
            525,
            172,
            240,
            10,
        )
        slicer("trade", "dim_trade_type", "trade_type_name", "Trade type", 230)
        slicer("mode", "dim_mode", "mode_name", "Domestic mode", 528)
        slicer("origin", "dim_origin_zone", "zone_name", "Origin zone", 826)
        slicer("destination", "dim_destination_zone", "zone_name", "Destination zone", 1124)
        if page == "lanes":
            cards = [
                ("Candidate Count", "Eligible lane-trade records"),
                ("Candidate Tonnage", "Eligible 2024 tonnage (ktons)"),
                ("Candidate CAGR", "Eligible 2024-2050 CAGR"),
                ("High Growth Lane Index", "Best growth-density index"),
            ]
        elif page == "scenarios":
            cards = [
                ("Baseline (billion tons)", "2024 freight (billion tons)"),
                ("Forecast (billion tons)", "2050 forecast (billion tons)"),
                ("Scenario Growth", "2024-2050 scenario growth"),
                ("Lane CAGR 2024-2050", "2024-2050 annual growth"),
            ]
        else:
            cards = [
                ("Tonnage (billion tons)", "Freight (billion tons)"),
                ("Freight Value ($T)", "Freight value (2017 USD T)"),
                ("Ton-Miles (T)", "Ton-miles (trillions)"),
                ("Value Density ($M/kton)", "Value density (2017 USD M/kton)"),
            ]
        for i, (m, label) in enumerate(cards):
            metric("kpi" + str(i), m, label, 230 + i * 298)
        if page == "overview":
            chart(
                "mode",
                "clusteredBarChart",
                "dim_mode",
                "mode_name",
                "Tonnage (ktons)",
                "Which modes carry the most tonnage? (ktons)",
                230,
                325,
                570,
                310,
            )
            chart(
                "trade",
                "clusteredBarChart",
                "dim_trade_type",
                "trade_type_name",
                "Freight Value ($M)",
                "Freight value by trade type (2017 USD M)",
                820,
                325,
                588,
                310,
            )
            table(
                "concentration",
                [
                    projection("fact_freight_flow", m, True)
                    for m in ["Top 10 Lane Concentration", "Top 10 Commodity Concentration"]
                ],
                "Concentration within the selected network",
                230,
                655,
                570,
                160,
            )
            text(
                "reading",
                "Use this report to choose lanes for investigation. High flow or growth does not prove a capacity shortage. Validate physical capacity, costs and service before committing resources.",
                820,
                655,
                588,
                170,
                12,
                NAVY,
            )
        elif page == "lanes":
            columns = [
                projection("dim_lane", "lane_name", label="Lane"),
                projection("dim_trade_type", "trade_type_name", label="Trade"),
            ] + [
                projection("fact_freight_flow", m, True, label)
                for m, label in [
                    ("Candidate Tonnage", "2024 ktons"),
                    ("Candidate Forecast", "2050 ktons"),
                    ("Candidate CAGR", "CAGR"),
                    ("High Growth Lane Index", "Index"),
                ]
            ]
            table(
                "candidates",
                columns,
                "Lane candidates  /  baseline >= 1,000 ktons and modes 1-6  /  sort any column",
                230,
                325,
                1178,
                380,
                [equal("fact_freight_flow", "Candidate Filter", 1, True)],
            )
            text(
                "reading",
                "Index = CAGR percentile x value-density percentile across all positive-baseline source lane-trade records. The index stays fixed when filters change. Within-zone flows are included. Review commodity mix and source-mode context.",
                230,
                725,
                1178,
                110,
                12,
                NAVY,
            )
        elif page == "modes":
            chart(
                "tonnage",
                "clusteredBarChart",
                "dim_mode",
                "mode_name",
                "Tonnage (ktons)",
                "Mode tonnage (ktons)",
                230,
                325,
                570,
                310,
            )
            chart(
                "value",
                "clusteredBarChart",
                "dim_mode",
                "mode_name",
                "Freight Value ($M)",
                "Mode freight value (2017 USD M)",
                820,
                325,
                588,
                310,
            )
            table(
                "shares",
                [projection("dim_mode", "mode_name", label="Mode")]
                + [
                    projection("fact_freight_flow", m, True)
                    for m in ["Tonnage (ktons)", "Mode Share", "Value Density ($M/kton)"]
                ],
                "Mode share removes only the mode filter from its denominator",
                230,
                655,
                1178,
                190,
            )
        elif page == "commodities":
            chart(
                "tonnage",
                "clusteredBarChart",
                "dim_commodity",
                "commodity_name",
                "Tonnage (ktons)",
                "Commodity tonnage  /  scroll for the full ranking (ktons)",
                230,
                325,
                570,
                490,
            )
            table(
                "density",
                [projection("dim_commodity", "commodity_name", label="Commodity")]
                + [
                    projection("fact_freight_flow", m, True)
                    for m in ["Tonnage (ktons)", "Freight Value ($M)", "Value Density ($M/kton)"]
                ],
                "Commodity scale and economic density",
                820,
                325,
                588,
                490,
            )
        else:
            chart(
                "trend",
                "lineChart",
                "dim_year",
                "year",
                "Tonnage (ktons)",
                "Estimate to source forecast (ktons)  /  three selected source years",
                230,
                325,
                730,
                310,
            )
            table(
                "values",
                [
                    projection("dim_year", "year"),
                    projection("dim_year", "scenario_type", label="Source basis"),
                ]
                + [
                    projection("fact_freight_flow", m, True)
                    for m in ["Tonnage (ktons)", "Freight Value ($M)"]
                ],
                "Compare source years",
                978,
                325,
                430,
                310,
            )
            text(
                "reading",
                "2024 is a source estimate. 2030 and 2050 are FAF forecast scenarios. CAGR uses a 26-year interval. This comparison describes possible flow growth; it does not estimate spare capacity, savings or service reliability.",
                230,
                660,
                1178,
                160,
                13,
                NAVY,
            )
        states = {
            v["name"]: {"singleVisual": {"objects": {"merge": v["visual"]["objects"]}}}
            for v in visuals
            if v["visual"]["visualType"] == "slicer"
        }
        save(
            definition / f"bookmarks/reset_{page}.bookmark.json",
            {
                "$schema": SCHEMA + "bookmark/2.1.0/schema.json",
                "displayName": "Reset " + page_title,
                "name": "reset_" + page,
                "options": {
                    "suppressActiveSection": True,
                    "suppressDisplay": True,
                    "applyOnlyToTargetVisuals": True,
                    "targetVisualNames": list(states),
                },
                "explorationState": {
                    "version": "1.0",
                    "activeSection": page,
                    "sections": {page: {"visualContainers": states}},
                },
            },
        )
        reset = visual(
            "reset",
            "actionButton",
            24,
            790,
            172,
            42,
            objects={
                "text": [
                    {"properties": {"show": literal(True)}},
                    {
                        "selector": {"id": "default"},
                        "properties": {
                            "text": literal("Reset filters"),
                            "fontSize": literal(11),
                            "fontColor": color(NAVY),
                        },
                    },
                ],
                "fill": [
                    {"properties": {"show": literal(True)}},
                    {"selector": {"id": "default"}, "properties": {"fillColor": color("#DCE5E8")}},
                ],
                "shape": props(tileShape=literal("rectangle")),
                "icon": props(show=literal(False)),
                "outline": props(show=literal(False)),
            },
        )
        reset["visual"]["visualContainerObjects"]["visualLink"] = props(
            show=literal(True), type=literal("Bookmark"), bookmark=literal("reset_" + page)
        )
        save(page_dir / "visuals" / reset["name"] / "visual.json", reset)
    save(
        definition / "bookmarks/bookmarks.json",
        {
            "$schema": SCHEMA + "bookmarksMetadata/1.0.0/schema.json",
            "items": [{"name": "reset_" + p[0]} for p in PAGES],
        },
    )
    print(
        "Created power_bi/FreightFlow.pbip: five pages, native filters, reset bookmarks and phone layouts."
    )


if __name__ == "__main__":
    main()
