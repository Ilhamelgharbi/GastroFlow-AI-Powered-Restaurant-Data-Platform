# Phase 1 data-quality rules

These are audit findings and transformation requirements, not changes to the
source files. Apply cleaning and enforce applicable rules in the later dbt
staging and testing phases.

| Rule / finding | Audit result | Follow-up |
|---|---|---|
| Never upload `_idx`, `email`, or `password`. | Sanitizer removed these columns; all seven ready files passed verification. | Keep the verification step before any upload. |
| Preserve original source CSVs during sanitization. | Sanitized copies are written under `data/ready/`. | Continue treating source files as read-only. |
| Primary identifiers expected to be unique must be tested. | All profiled IDs were unique except `menu.menu_id`, which has 131,361 duplicates. | Do not declare `menu_id` a primary key; investigate a suitable key before modeling. |
| Validate child-to-parent identifiers. | 273 `menu.r_id` values did not match a restaurant; all other audited relationships had zero unmatched rows. | Document the exception and choose an explicit policy before enforcing dbt relationships. |
| Treat blank and placeholder values deliberately. | Restaurant `rating` has 87,014 `--` values; several restaurant and food fields have blanks. | Normalize placeholders and blanks to null in staging where appropriate. |
| Parse numeric and currency fields explicitly. | 148,410 restaurant `cost` values contain `₹`; `rating_count` failed the audit's integer cast check for all 148,541 rows. | Inspect source representations and define tested parsing rules; do not infer types at ingestion. |
| Split location values only after confirming the source convention. | 101,712 restaurant `city` values contain commas. | Confirm whether these encode area and city, then split and test in staging. |
| Account for expected missing order attributes. | 3,592,803 `customer_rating` and 849,878 `delivery_time_min` values are blank. | Preserve nulls and define metric denominators explicitly. |
| Restrict statuses to observed values after validating the source. | `Delivered`, `Cancelled`, and `Refunded` were observed. | Use accepted-values tests based on the verified domain; keep business logic explicit. |
| Do not infer order-item-to-menu mapping. | `order_items` has no `menu_id`. | Validate any proposed composite-key bridge before joining. |
| Keep review records even when review text is blank. | The audit found zero blank comments; all 300,000 rows remain in the prepared file. | If blanks occur in future data, retain the review for rating/count analytics and filter text only in enrichment logic. |

Profiling counts and field-level details are in [profiling_report.txt](profiling_report.txt).
