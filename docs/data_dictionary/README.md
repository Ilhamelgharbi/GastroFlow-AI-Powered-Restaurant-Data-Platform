# Data dictionary

This dictionary describes the sanitized CSV headers and row counts observed
during the local Phase 1 audit. CSV fields are treated as text at this stage;
types and cleaning rules belong to the transformation phase. Descriptions are
based on field names and should be confirmed against business definitions
before they are used for reporting.

The audit covered 35,098,217 rows across seven files. Source data and sanitized
CSV files remain local and are not included in this repository.

| File | Rows | Fields |
|---|---:|---|
| [restaurants.md](restaurants.md) | 148,541 | 11 |
| [users.md](users.md) | 100,000 | 9 |
| [food.md](food.md) | 371,561 | 3 |
| [menu.md](menu.md) | 1,179,936 | 5 |
| [orders.md](orders.md) | 10,000,000 | 19 |
| [order_items.md](order_items.md) | 22,998,179 | 7 |
| [reviews.md](reviews.md) | 300,000 | 7 |

See [relationships.md](relationships.md) for audited key relationships and
the ERD, and [data_quality_rules.md](data_quality_rules.md) for audit findings
and rules to apply or test in later transformation work.
