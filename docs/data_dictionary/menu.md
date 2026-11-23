# `menu.csv`

Rows: **1,179,936**. The exported index column was removed during
sanitization. `menu_id` has 131,361 duplicate values, so it is not a unique
key in the audited data.

| Field | Description / audit note |
|---|---|
| `menu_id` | Source menu identifier; 131,361 duplicate values. Do not use as a unique key without further investigation. |
| `r_id` | Restaurant identifier; 273 rows do not match `restaurants.id`. |
| `f_id` | Food identifier; all audited values match `food.f_id`. |
| `cuisine` | Source cuisine field. |
| `price` | Source menu price; type and currency convention not established in this audit. |
