# GastroFlow dbt transformations

This dbt BigQuery project transforms the `gastroflow_raw` source tables into
staging views, marts, and historical snapshots.

## Run from the repository root

```powershell
.\.venv\Scripts\dbt.exe debug --project-dir transformation
.\.venv\Scripts\dbt.exe build --project-dir transformation --select staging marts
.\.venv\Scripts\dbt.exe snapshot --project-dir transformation --select snap_restaurants snap_orders
```

Snapshots write to `gastroflow_snapshots`. Both examples use dbt's `check`
strategy because their sources do not provide a reliable last-updated timestamp:

- `snap_restaurants` keeps history when restaurant details change.
- `snap_orders` keeps history when an order's status or sales amount changes.

The first snapshot run records the current values as a baseline. To verify a
new history version, change a tracked value in a non-production source and run
the snapshot command again. Each snapshot row includes dbt validity fields such
as `dbt_valid_from` and `dbt_valid_to`.
