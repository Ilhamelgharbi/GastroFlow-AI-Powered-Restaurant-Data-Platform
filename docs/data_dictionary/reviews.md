# `reviews.csv`

Rows: **300,000**. `review_id` is unique in the audited file. No null or blank
comments were reported; there are 294 distinct comment values.

| Field | Description / audit note |
|---|---|
| `review_id` | Review identifier; unique in the audited file. |
| `order_id` | Order identifier; all audited values match `orders.order_id`. |
| `user_id` | User identifier; all audited values match `users.user_id`. |
| `restaurant_id` | Restaurant identifier; all audited values match `restaurants.id`. |
| `rating` | Source review rating; type and allowed range not established in this audit. |
| `comment` | Review text; no null or blank values reported and 294 distinct values observed. |
| `review_date` | Source review date; parsing rules not established in this audit. |
