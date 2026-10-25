# FreightFlow

FreightFlow examines U.S. freight lanes, transport modes and commodities using the supplied Freight Analysis Framework 5.7.1 snapshot. Python prepares the data, MySQL provides an analytical database, and Excel and Power BI support review.

The question is practical: **which freight lanes deserve further capacity investigation?** Read [the problem and solution](PROBLEM_AND_SOLUTION.md) for the method, findings and limitations.

## What the data means

FAF provides aggregate estimates, not individual shipments. Tonnage is in **thousand tons (ktons)**, freight value in **millions of 2017 USD**, and activity in **million ton-miles**. The project uses the 2024 estimate as its baseline and 2030 and 2050 source forecasts as scenarios. It cannot establish actual capacity shortages, service quality, costs or savings.

The supplied snapshot contains 2,671,386 source rows. Aggregating foreign-route and distance-band detail produces 3,950,145 fact rows across the three selected years. Each fact row represents origin zone, destination zone, commodity, mode, trade type and year.

## Structure

```text
src/freightflow/  Small Python modules for profiling, transformation and analysis
notebooks/       Four learning notebooks and an optional notebook runner
sql/             Ordered MySQL scripts and a password-prompting loader
excel/           Workbook inputs and presentation builder
power_bi/        DAX, Power Query example, theme and editable report project
data/            Local source and generated tables
docs/            Data and metric dictionaries
artifacts/       Local checks, findings and executed notebooks
outputs/         Local Excel workbook
```

Local editor state, credentials, raw data, generated datasets, binary reports and detailed learning notes are ignored. README.md and PROBLEM_AND_SOLUTION.md are the two public Markdown files. Original planning documents are kept locally in archive/.

## Run the project

Use Python 3.12 or 3.13, MySQL 8 and Power BI Desktop. Open a terminal in the project folder. Run commands separately and stop on an error.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[dev]'
```

Download the [FAF5.7.1 dataset and metadata](https://faf.ornl.gov/faf5/Default.aspx) and put FAF5.7.1.csv and FAF5_metadata.xlsx in data/raw/FAF5.7.1/. Preserve the original files. Newer releases may have a different schema; this project targets this exact snapshot.

```powershell
.\.venv\Scripts\python.exe -m freightflow.cli profile
.\.venv\Scripts\python.exe -m freightflow.cli transform
.\.venv\Scripts\python.exe -m freightflow.cli analyze
.\.venv\Scripts\python.exe -m pytest -q
```

The profile counts and checks key uniqueness across the full source, and inspects its first 100,000 rows in detail. Transformation checks every selected year-record for missing, negative, nonfinite and unknown-code values. It sums repeated model keys rather than discarding records. Analysis compares 27 raw-source totals with the published tables. Any failed reconciliation stops publication.

The fact and dimensions are written as CSV and Parquet in data/processed/. Findings and validation results go to artifacts/. To learn cell by cell, open notebooks 01 through 04 with the project's Python environment. The optional runner executes the same cells and saves output copies locally:

```powershell
.\.venv\Scripts\python.exe notebooks/run_notebooks.py
```

## Build MySQL

Start MySQL and use your own local login. The loader prompts for a password without displaying or saving it. It modifies only the freightflow schema. It replaces the project's staging and fact contents, so retain unrelated work in another schema.

```powershell
.\.venv\Scripts\python.exe sql/run_mysql.py --host localhost --port 3306 --user root
```

The loader runs each numbered SQL section in order, loads dimensions before facts and writes artifacts/quality/mysql_reconciliation.csv. All 27 comparisons must pass. If LOCAL INFILE is disabled, it uses parameterized batch inserts without changing the server setting. Reloading several million indexed rows can take several minutes.

In IntelliJ, select the **freightflow** schema in the connection's Schemas tab and set the SQL dialect to MySQL. A connection display name can differ from its selected schema.

## Excel

```powershell
.\.venv\Scripts\python.exe excel/prepare_inputs.py
node excel/build_workbook.mjs
```

The workbook is saved as outputs/freightflow/FreightFlow_Operations.xlsx. Overview has year/trade selectors, linked KPIs, mode shares and a scenario comparison. Lane review contains the top 250 eligible candidates; its filters affect that shortlist only. Source tables expose the inputs, and Checks recomputes reconciliation differences.

The presentation builder requires the **Codex artifact runtime** providing @oai/artifact-tool. It is not a public npm dependency. For an ordinary Excel installation, reproduce the workbook by importing the generated KPI and mode CSVs as tables, using SUMIFS for year/trade totals, dividing mode totals by the matching KPI total, and importing the candidate CSV for a filterable shortlist. Keep the source snapshot and filtering definitions identical. The detailed local runbook includes the exact formulas and refresh checks.

## Power BI

```powershell
.\.venv\Scripts\python.exe power_bi/build_report.py
```

Open power_bi/FreightFlow.pbip in Desktop and select **Refresh now**. Five pages cover the freight network, lane priorities, mode mix, commodities and growth scenarios. Native slicers, reset bookmarks, sortable tables and phone layouts are included. Hold Ctrl when following navigation buttons in Desktop edit mode. Save as PBIX for a single report file.

The report imports the checked local CSV snapshot also loaded into MySQL. It does not claim a live MySQL connection. power_query.m shows the optional MySQL connector pattern. On another machine, rerun the builder or update the DataFolder parameter before refresh. The generated semantic model contains that local path and is ignored by Git.

## Read results carefully

For all trade types, the supplied 2024 estimate totals about **20.012 billion tons**. The 2050 source scenario is about **28.890 billion tons**, approximately **44.4% higher**. These are scenario comparisons, not measured business improvements.

The lane index multiplies CAGR and value-density percentiles across positive-baseline lane-trade records. Candidate review additionally requires at least 1,000 ktons in 2024 and modes 1-6. The index stays fixed under report filters; it is a screening aid, not a forecast model or optimizer. Within-zone flows are included and must be interpreted as regional flows.
