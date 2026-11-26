from ai.enrich_reviews import ReviewLabels, normalize
from ai.sql_safety import is_safe


def test_normalize_clamps_and_cleans():
    out = normalize(ReviewLabels(sentiment_label="negative", sentiment_score=-3,
                                 topic="delivery", key_issue=" null "))
    assert out["sentiment_score"] == -1.0
    assert out["key_issue"] is None


def test_normalize_truncates_issue():
    out = normalize(ReviewLabels(sentiment_label="neutral", sentiment_score=0.2,
                                 topic="other", key_issue="x" * 300))
    assert len(out["key_issue"]) == 100


def test_safe_select_allowed():
    assert is_safe("SELECT city, SUM(gmv) FROM mart_daily_city_revenune GROUP BY 1 LIMIT 10")[0]
    assert is_safe("WITH a AS (SELECT 1) SELECT * FROM a")[0]


def test_unsafe_sql_blocked():
    assert not is_safe("DROP TABLE fct_orders")[0]
    assert not is_safe("SELECT 1; DELETE FROM fct_orders")[0]
    assert not is_safe("SELECT * FROM `p.gastroflow_raw.users`")[0]
    assert not is_safe("SELECT email FROM dim_customers")[0]
    assert not is_safe("SELECT * FROM `p.other_ds.t`")[0]


def test_column_names_with_keywords_not_blocked():
    assert is_safe("SELECT order_status, updated_flag FROM fct_orders")[0]
