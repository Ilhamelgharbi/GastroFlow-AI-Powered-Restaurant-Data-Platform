# `orders.csv`

Rows: **10,000,000**. No null or blank values were reported except where noted.
`order_id` is unique in the audited file.

| Field | Description / audit note |
|---|---|
| `order_id` | Order identifier; unique in the audited file. |
| `order_timestamp` | Source order timestamp; parsing and timezone rules not established in this audit. |
| `order_date` | Source order date. |
| `user_id` | User identifier; all audited values match `users.user_id`. |
| `r_id` | Restaurant identifier; all audited values match `restaurants.id`. |
| `restaurant_city` | Source restaurant-city field. |
| `cuisine` | Source cuisine field. |
| `items_count` | Source item-count field; type and definition not established in this audit. |
| `sales_qty` | Source sales-quantity field; type and definition not established in this audit. |
| `subtotal` | Source subtotal; currency and calculation convention not established in this audit. |
| `discount` | Source discount; currency and calculation convention not established in this audit. |
| `delivery_fee` | Source delivery-fee amount; currency convention not established in this audit. |
| `gst` | Source GST amount; calculation convention not established in this audit. |
| `sales_amount` | Source sales amount; currency and calculation convention not established in this audit. |
| `currency` | Source currency code or label. |
| `payment_method` | Payment category: UPI 4,599,971; Card 1,998,893; Wallet 1,500,031; COD 1,401,129; NetBanking 499,976. |
| `order_status` | Status: Delivered 9,150,122; Cancelled 599,251; Refunded 250,627. |
| `customer_rating` | Customer rating; 3,592,803 null or blank values. |
| `delivery_time_min` | Delivery time in minutes; 849,878 null or blank values. |
