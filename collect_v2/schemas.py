"""Source CSV headers and matching all-STRING BigQuery RAW column names."""

import csv
import re
from pathlib import Path

SOURCE_HEADERS: dict[str, tuple[str, ...]] = {
    "restaurants": (
        "",
        "id",
        "name",
        "city",
        "rating",
        "rating_count",
        "cost",
        "cuisine",
        "lic_no",
        "link",
        "address",
        "menu",
    ),
    "users": (
        "",
        "user_id",
        "name",
        "email",
        "password",
        "Age",
        "Gender",
        "Marital Status",
        "Occupation",
        "Monthly Income",
        "Educational Qualifications",
        "Family size",
    ),
    "food": ("", "f_id", "item", "veg_or_non_veg"),
    "menu": ("", "menu_id", "r_id", "f_id", "cuisine", "price"),
    "orders": (
        "order_id",
        "order_timestamp",
        "order_date",
        "user_id",
        "r_id",
        "restaurant_city",
        "cuisine",
        "items_count",
        "sales_qty",
        "subtotal",
        "discount",
        "delivery_fee",
        "gst",
        "sales_amount",
        "currency",
        "payment_method",
        "order_status",
        "customer_rating",
        "delivery_time_min",
    ),
    "order_items": (
        "order_item_id",
        "order_id",
        "r_id",
        "f_id",
        "price",
        "quantity",
        "line_amount",
    ),
    "reviews": (
        "review_id",
        "order_id",
        "user_id",
        "restaurant_id",
        "rating",
        "comment",
        "review_date",
    ),
}


def _bigquery_column_name(header: str) -> str:
    if not header.strip():
        return "source_index"
    return re.sub(r"[^a-z0-9_]+", "_", header.strip().lower()).strip("_")


RAW_COLUMNS: dict[str, list[str]] = {
    table: [_bigquery_column_name(header) for header in headers]
    for table, headers in SOURCE_HEADERS.items()
}
TABLES: tuple[str, ...] = tuple(SOURCE_HEADERS)


def source_csv_path(directory: Path, table: str) -> Path:
    if table not in SOURCE_HEADERS:
        raise ValueError(f"Unknown table: {table}")
    return directory / table / f"{table}.csv"


def assert_source_header(table: str, path: Path) -> None:
    if table not in SOURCE_HEADERS:
        raise ValueError(f"Unknown table: {table}")

    with path.open(encoding="utf-8-sig", newline="") as stream:
        actual = tuple(next(csv.reader(stream), ()))

    expected = SOURCE_HEADERS[table]
    if actual != expected:
        raise ValueError(
            f"{path}: source header does not match the expected {table} header; "
            f"expected {expected!r}, got {actual!r}"
        )
