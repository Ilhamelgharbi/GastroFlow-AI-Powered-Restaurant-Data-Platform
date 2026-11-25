-- Reports delivered-order counts and exact delivery-time percentiles by city and hour.
-- PERCENTILE_CONT computes exact percentiles; QUALIFY returns one row per city and hour.
select
    city,
    extract(hour from order_timestamp) as order_hour,
    count(*) over (
        partition by city, extract(hour from order_timestamp)
    ) as delivered_orders,
    round(
        percentile_cont(safe_cast(delivery_time_min as numeric), 0.5)
            over (partition by city, extract(hour from order_timestamp)),
        1
    ) as p50,
    round(
        percentile_cont(safe_cast(delivery_time_min as numeric), 0.9)
            over (partition by city, extract(hour from order_timestamp)),
        1
    ) as p90
from {{ ref('fct_orders') }}
where is_delivered
qualify row_number() over (
    partition by city, extract(hour from order_timestamp)
    order by order_timestamp
) = 1