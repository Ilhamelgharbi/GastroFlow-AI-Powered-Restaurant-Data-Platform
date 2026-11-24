-- Builds a reusable calendar dimension for dates from 2024 through 2026.
-- GENERATE_DATE_ARRAY creates one row per day; EXTRACT derives calendar fields.
{{ config(materialized='table') }}

WITH spine AS (
    SELECT date_day
    FROM UNNEST(
        GENERATE_DATE_ARRAY(
            DATE '2024-01-01',
            DATE '2026-12-31',
            INTERVAL 1 DAY
        )
    ) AS date_day
)

SELECT
    date_day,
    EXTRACT(YEAR FROM date_day) AS year,
    EXTRACT(MONTH FROM date_day) AS month,
    FORMAT_DATE('%B', date_day) AS month_name,
    FORMAT_DATE('%A', date_day) AS day_name,
    EXTRACT(DAYOFWEEK FROM date_day) IN (1, 7) AS is_weekend
FROM spine