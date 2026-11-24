-- Phase 1: parse sales text into NUMERIC values for BigQuery aggregations.
-- Phase 2: summarize order and delivered-sales metrics by date and city.
with orders as (
    select
        order_date,
        city,
        is_delivered,
        order_status,
        safe_cast(sales_amount as numeric) as sales_amount
    from {{ ref('fct_orders') }}
),
daily_totals as (
    select
        order_date,
        city,
        count(*) as orders,
        countif(is_delivered) as delivered_orders,
        countif(order_status = 'Cancelled') as cancelled_orders,
        sum(if(is_delivered, sales_amount, 0)) as gmv
    from orders
    group by 1, 2
)

select
    order_date,
    city,
    orders,
    delivered_orders,
    round(safe_divide(cancelled_orders, orders), 4) as cancel_rate,
    gmv,
    round(
        if(delivered_orders = 0, 0, safe_divide(gmv, delivered_orders)),
        2
    ) as aov
from daily_totals