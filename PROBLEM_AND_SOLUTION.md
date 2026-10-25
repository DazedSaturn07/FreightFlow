# Problem and solution

## Problem

A freight planning analyst needs to identify which U.S. freight flows deserve further investigation. Large baseline volume, forecast growth and economic density each describe something different. Looking only at the fastest-growing lane can promote a tiny baseline; looking only at value can overlook bulk transport needs.

The source is the Freight Analysis Framework 5.7.1 dataset, published by the Bureau of Transportation Statistics with Federal Highway Administration support. It contains regional aggregate estimates. It does not contain vehicle availability, spare network capacity, shipment lead times, operating costs or carrier service levels.

## Solution

FreightFlow turns the supplied snapshot into a consistent Python, MySQL, Excel and Power BI workflow:

1. Count and profile the source while preserving its original files.
2. Check every selected year-record for missing, nonfinite and negative metrics, and reject unknown dimension codes.
3. Sum foreign-route and distance-band detail into one row per origin, destination, commodity, mode, trade type and year.
4. Calculate tonnage, value, ton-miles, mode share, concentration, value density and scenario growth.
5. Screen lane-trade records using growth and value-density percentiles, then review candidates with at least 1,000 ktons in 2024 and modes 1-6.
6. Reconcile raw-source, Python and MySQL totals before using the workbook and dashboard.

Python uses DuckDB to aggregate the large CSV efficiently and pandas to read metadata and prepare small report tables. DuckDB is a local processing library; **MySQL 8 is the project database**. The report imports the same validated CSV snapshot, avoiding a connector-driver requirement.

## Outputs

| Output | Use |
| --- | --- |
| Clean fact, dimensions and marts | Repeatable analysis with a declared row meaning |
| MySQL schema and analytical views | SQL queries, relational integrity and independent totals |
| Excel workbook | Year/trade comparison, a filterable 250-record shortlist and visible checks |
| Five-page Power BI report | Network, lane, mode, commodity and forecast exploration |
| Quality and findings files | Reviewable evidence and proposed next investigations |

## Findings from the supplied snapshot

- Across all trade types, the 2024 estimate is **20,011,502.95 ktons**, or about **20.012 billion tons**.
- The 2050 source scenario totals **28,890,491.21 ktons**, about **44.37% higher** than the 2024 estimate. This is a source scenario, not a measured improvement or a promise.
- Truck accounts for about **67.43%** of domestic baseline tonnage; pipeline contributes about **19.74%**. These are tonnage shares, not shipment-count or revenue shares.
- **2,031 lane-trade records** meet the candidate baseline and mode rules. The workbook exposes the top 250; the Power BI candidate page covers the full eligible set.
- Several leading index candidates are within-zone flows. They describe regional freight, so the analyst should inspect commodity mix and local network context before calling them corridors.

The practical outcome is a documented shortlist for investigation. Next, obtain infrastructure capacity, utilization, cost and service data for the selected lanes. Those additional sources are necessary before proposing capacity investment or claiming savings.

## Important definitions

- **Tonnage:** sum of thousand tons. Multiply ktons by 1,000 to express tons.
- **Value:** sum of millions of 2017 U.S. dollars. It describes freight value, not operator revenue or profit.
- **Mode share:** selected-mode tonnage divided by tonnage with only the mode filter removed.
- **Top 10 concentration:** the ten largest lane or commodity totals divided by the matching selected population. Lane identity includes origin, destination and domestic mode; trade filters remain in context.
- **Value density:** total freight value divided by total tonnage, not an average of row-level ratios.
- **CAGR:** `(2050 tonnage / 2024 tonnage)^(1/26) - 1`, only for positive endpoints.
- **Growth-density index:** growth percentile multiplied by value-density percentile across positive-endpoint lane-trade records. Global scores stay fixed under report filters.

## Limitations

The 2024 baseline is an estimate. The 2030 and 2050 values are FAF source forecasts. Within-zone flows and aggregate domestic legs of international trade need careful interpretation. A high index does not establish a shortage, feasibility, causality or financial return. Forecast-year flows must not be added to baseline flows and described as one annual total.

See the [official FAF source and units](https://www.bts.gov/faf/faf5) and [FAF download portal](https://faf.ornl.gov/faf5/Default.aspx). The original retrieval date of the supplied files is unknown; the local manifest records verification time and a checksum instead of inventing a retrieval date.
