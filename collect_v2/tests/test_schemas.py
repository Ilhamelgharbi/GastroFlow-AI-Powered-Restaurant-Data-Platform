from pathlib import Path

import pytest

from collect_v2.schemas import RAW_COLUMNS, SOURCE_HEADERS, assert_source_header


def test_source_and_bigquery_schemas_have_matching_column_counts():
    assert set(SOURCE_HEADERS) == set(RAW_COLUMNS)
    for table in SOURCE_HEADERS:
        assert len(SOURCE_HEADERS[table]) == len(RAW_COLUMNS[table])


def test_source_header_with_blank_export_index_is_preserved(tmp_path):
    path = tmp_path / "food.csv"
    path.write_text(",f_id,item,veg_or_non_veg\n0,f1,Meal,Veg\n", encoding="utf-8")

    assert_source_header("food", path)


def test_source_header_rejects_mismatched_columns(tmp_path):
    path = tmp_path / "food.csv"
    path.write_text("f_id,item\nf1,Meal\n", encoding="utf-8")

    with pytest.raises(ValueError, match="source header does not match"):
        assert_source_header("food", path)


def test_all_sample_csv_headers_match_source_contract():
    sample_dir = Path(__file__).resolve().parents[2] / "data" / "sample"

    for table in SOURCE_HEADERS:
        assert_source_header(table, sample_dir / table / f"{table}.csv")
