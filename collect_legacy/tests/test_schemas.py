"""Privacy guard: sensitive columns must never appear in a RAW schema."""
from collect.schemas import FORBIDDEN_COLUMNS, RAW_COLUMNS, TABLES


def test_no_sensitive_columns_in_any_schema():
    for table, columns in RAW_COLUMNS.items():
        assert not FORBIDDEN_COLUMNS & {c.lower() for c in columns}, table


def test_all_seven_tables_defined():
    assert len(TABLES) == 7


def test_no_duplicate_column_names_per_table():
    for table, columns in RAW_COLUMNS.items():
        assert len(columns) == len(set(columns)), table