import pytest

from collect.lib.validation import (
    assert_matches_schema,
    assert_no_sensitive_columns,
    count_rows,
    csv_columns,
)


def test_csv_columns_normalizes_header(tmp_path):
    path = tmp_path / "source.csv"
    path.write_text("\ufeff ID , Name \n1,Ada\n", encoding="utf-8")

    assert csv_columns(path) == ["id", "name"]


def test_csv_columns_rejects_empty_header(tmp_path):
    path = tmp_path / "empty_header.csv"
    path.write_text(",name\n1,Ada\n", encoding="utf-8")

    with pytest.raises(ValueError, match="empty or invalid header"):
        csv_columns(path)


def test_sensitive_columns_are_rejected(tmp_path):
    path = tmp_path / "users.csv"
    path.write_text(
        "user_id,email,password\n1,a@example.test,secret\n", encoding="utf-8"
    )

    with pytest.raises(ValueError, match="email, password"):
        assert_no_sensitive_columns(path)


def test_safe_headers_pass_sensitive_column_check(tmp_path):
    path = tmp_path / "food.csv"
    path.write_text("f_id,item,veg_or_non_veg\nf1,meal,Veg\n", encoding="utf-8")

    assert_no_sensitive_columns(path)


def test_schema_column_count_is_checked(tmp_path):
    path = tmp_path / "food.csv"
    path.write_text("f_id,item\nf1,meal\n", encoding="utf-8")

    with pytest.raises(ValueError, match="2 columns.*expects 3"):
        assert_matches_schema("food", path)


def test_unknown_table_schema_is_rejected(tmp_path):
    with pytest.raises(ValueError, match="Unknown table: other"):
        assert_matches_schema("other", tmp_path / "other.csv")


def test_count_rows_handles_quoted_newlines(tmp_path):
    path = tmp_path / "reviews.csv"
    path.write_text(
        'review_id,comment\n1,"first line\nsecond line"\n2,plain\n',
        encoding="utf-8",
    )

    assert count_rows(path) == 2
