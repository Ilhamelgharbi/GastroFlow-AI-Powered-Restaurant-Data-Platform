# `order_items.csv`

Rows: **22,998,179**. `order_item_id` is unique in the audited file. No null or
blank values were reported in the audited fields.

| Field | Description / audit note |
|---|---|
| `order_item_id` | Order-line identifier; unique in the audited file. |
| `order_id` | Order identifier; all audited values match `orders.order_id`. |
| `r_id` | Restaurant identifier; no direct relationship check was specified in the audit. |
| `f_id` | Food identifier; all audited values match `food.f_id`. |
| `price` | Source line-item price; currency convention not established in this audit. |
| `quantity` | Source item quantity; type and valid range not established in this audit. |
| `line_amount` | Source line amount; calculation convention not established in this audit. |

There is no `menu_id` in this file. Do not infer a direct order-item-to-menu
relationship from restaurant and food identifiers alone.
