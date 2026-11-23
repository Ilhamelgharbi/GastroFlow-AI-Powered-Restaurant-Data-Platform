"""Profile the 7 source CSVs: counts, nulls, duplicate keys, orphan foreign keys."""
from pathlib import Path
import duckdb

READY = Path("data/ready")
TABLES = ["restaurants", "users", "food", "menu", "orders", "order_items", "reviews"]

# table -> primary key column (check these against your real headers)
PK = {
    "restaurants": "id", "users": "user_id", "food": "f_id", "menu": "menu_id",
    "orders": "order_id", "order_items": "order_item_id", "reviews": "review_id",
}
# child.column -> parent.column
FK = [
    ("orders", "user_id", "users", "user_id"),
    ("orders", "r_id", "restaurants", "id"),
    ("order_items", "order_id", "orders", "order_id"),
    ("order_items", "f_id", "food", "f_id"),
    ("menu", "r_id", "restaurants", "id"),
    ("menu", "f_id", "food", "f_id"),
    ("reviews", "order_id", "orders", "order_id"),
    ("reviews", "user_id", "users", "user_id"),
    ("reviews", "restaurant_id", "restaurants", "id"),
]

con = duckdb.connect()
for t in TABLES:
    path = (READY / f"{t}.csv").as_posix()
    con.execute(
        f"CREATE OR REPLACE VIEW {t} AS "
        f"SELECT * FROM read_csv('{path}', header=true, all_varchar=true, sample_size=-1)"
    )

def q(sql):
    return con.execute(sql).fetchall()

print("== Row counts and null counts ==")
for t in TABLES:
    n = q(f"SELECT count(*) FROM {t}")[0][0]
    cols = [r[0] for r in q(f"DESCRIBE {t}")]
    nulls = {
        c: q(f'SELECT count(*) FROM {t} WHERE "{c}" IS NULL OR trim("{c}") = \'\'')[0][0]
        for c in cols
    }
    print(f"\n{t}: {n:,} rows")
    for c, k in nulls.items():
        if k:
            print(f"  {c}: {k:,} null/blank ({k / n:.1%})")

print("\n== Duplicate primary keys ==")
for t, pk in PK.items():
    try:
        d = q(f'SELECT count(*) - count(DISTINCT "{pk}") FROM {t}')[0][0]
        print(f"{t}.{pk}: {d:,} duplicates")
    except Exception as e:
        print(f"{t}.{pk}: skipped ({e})")

print("\n== Orphan foreign keys ==")
for child, ccol, parent, pcol in FK:
    try:
        o = q(
            f'SELECT count(*) FROM {child} c LEFT JOIN {parent} p '
            f'ON c."{ccol}" = p."{pcol}" WHERE c."{ccol}" IS NOT NULL AND p."{pcol}" IS NULL'
        )[0][0]
        print(f"{child}.{ccol} -> {parent}.{pcol}: {o:,} orphans")
    except Exception as e:
        print(f"{child}.{ccol}: skipped ({e})")

print("\n== Messy restaurant values ==")
for label, sql in {
    "rating = '--'": "SELECT count(*) FROM restaurants WHERE rating = '--'",
    "cost with currency symbol": "SELECT count(*) FROM restaurants WHERE cost LIKE '%₹%'",
    "city with comma": "SELECT count(*) FROM restaurants WHERE city LIKE '%,%'",
    "rating_count not numeric": "SELECT count(*) FROM restaurants WHERE try_cast(rating_count AS INTEGER) IS NULL",
}.items():
    print(f"{label}: {q(sql)[0][0]:,}")

print("\n== Categorical values worth knowing ==")
for sql in [
    "SELECT order_status, count(*) FROM orders GROUP BY 1 ORDER BY 2 DESC",
    "SELECT payment_method, count(*) FROM orders GROUP BY 1 ORDER BY 2 DESC",
]:
    print(sql, "->", q(sql))

print("\n== Reviews ==")
print("blank comments:", q("SELECT count(*) FROM reviews WHERE comment IS NULL OR trim(comment) = ''")[0][0])
print("distinct comments:", q("SELECT count(DISTINCT comment) FROM reviews")[0][0])
