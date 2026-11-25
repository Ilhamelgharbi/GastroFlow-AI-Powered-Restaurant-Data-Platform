-- Provides order-item measures and the related order's time and location.
-- SAFE_CAST produces a TIMESTAMP for event-time comparisons in incremental runs.
{{ config(materialized='incremental', unique_key='order_item_id', incremental_strategy='merge', on_schema_change='append_new_columns') }}

select
    oi.order_item_id,
    oi.order_id,
    oi.restaurant_id,
    oi.f_id,
    safe_cast(o.order_timestamp as timestamp) as order_ts,
    o.order_date,
    o.city,
    oi.price,
    oi.quantity,
    oi.line_amount
from {{ ref('stg_order_items') }} oi
inner join {{ ref('fct_orders') }} o using (order_id)
{% if is_incremental() %}
where safe_cast(o.order_timestamp as timestamp) > (
    select coalesce(max(order_ts), timestamp('1900-01-01'))
    from {{ this }}
)
{% endif %}