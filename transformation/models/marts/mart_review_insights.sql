-- Built only when dbt runs with --vars '{enable_ai: true}' (the Composer DAG does this
-- after ai_enrich_reviews has filled gastroflow_ai.review_enriched).
-- COUNTIF counts reviews with a flagged issue without needing a separate filter.
{{ config(enabled=var('enable_ai', false), tags=['ai']) }}

select
    rr.city,
    e.topic,
    e.sentiment_label,
    count(*) as reviews,
    round(avg(e.sentiment_score), 3) as avg_sentiment_score,
    round(avg(rr.rating), 2) as avg_star_rating,
    countif(e.key_issue is not null) as flagged_issues
from {{ source('ai', 'review_enriched') }} e
inner join {{ ref('stg_reviews') }} rr using (review_id)
group by 1, 2, 3