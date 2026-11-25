"""Fail if any ready file still has _idx, email or password headers."""
import sys
from pathlib import Path
import duckdb

READY = Path("data/ready")
FORBIDDEN = {"_idx", "email", "password"}

def main() -> int:
    con = duckdb.connect()
    bad = []
    for f in sorted(READY.glob("*.csv")):
        cols = [r[0].strip().lower() for r in con.execute(
            f"DESCRIBE SELECT * FROM read_csv_auto('{f.as_posix()}', all_varchar=true)"
        ).fetchall()]
        hit = FORBIDDEN & set(cols)
        print(f"{f.name}: {len(cols)} columns", "OK" if not hit else f"FORBIDDEN {hit}")
        if hit:
            bad.append((f.name, hit))
    return 1 if bad else 0

if __name__ == "__main__":
    sys.exit(main())
