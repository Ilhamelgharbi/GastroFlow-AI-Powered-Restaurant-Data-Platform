"""Explicit RAW table definitions.

Bronze keeps every column as STRING so a bad value can never fail a load.
Casting to real types happens later, in dbt staging, with SAFE_CAST.
Columns are matched BY POSITION, so the order below must equal the CSV order.
VERIFY these lists against the output of collect/profile.py before loading.
"""

RAW_COLUMNS: dict[str, list[str]] = {
    "restaurants": [
        "id", "name", "city", "rating", "rating_count", "cost",
        "cuisine", "lic_no", "link", "address", "menu",
    ],
    # email and password are intentionally absent
    "users": [
        "user_id", "name", "age", "gender", "marital_status",
        "occupation", "monthly_income", "education", "family_size",
    ],
    "food": ["f_id", "item", "veg_or_non_veg"],
    "menu": ["menu_id", "r_id", "f_id", "cuisine", "price"],
    "orders": [
        "order_id", "order_timestamp", "order_date", "user_id", "r_id",
        "restaurant_city", "cuisine", "items_count", "sales_qty", "subtotal",
        "discount", "delivery_fee", "gst", "sales_amount", "currency",
        "payment_method", "order_status", "customer_rating", "delivery_time_min",
    ],
    "order_items": [
        "order_item_id", "order_id", "r_id", "f_id", "price", "quantity", "line_amount",
    ],
    "reviews": [
        "review_id", "order_id", "user_id", "restaurant_id", "rating", "comment", "review_date",
    ],
}

TABLES: tuple[str, ...] = tuple(RAW_COLUMNS)

# Column names that must never reach GCS or BigQuery.
FORBIDDEN_COLUMNS: frozenset[str] = frozenset({"_idx", "email", "password"})