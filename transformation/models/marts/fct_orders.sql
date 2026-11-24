-- Provides one row per order for sales, delivery, and customer analysis.
-- SAFE_CAST makes the source timestamp comparable to the stored incremental watermark.
{{ config(materialized='incremental', unique_key='order_id', incremental_strategy='merge', on_schema_change='append_new_columns') }}

select
    order_id,
    safe_cast(order_timestamp as timestamp) as order_timestamp,
    order_date,
    customer_id,
    restaurant_id,
    city,
    cuisine,
    payment_method,
    order_status,
    is_delivered,
    items_count,
    sales_qty,
    subtotal,
    discount,
    delivery_fee,
    gst,
    sales_amount,
    customer_rating,
    delivery_time_min
from {{ ref('stg_orders') }}
{% if is_incremental() %}
where safe_cast(order_timestamp as timestamp) > (
    select coalesce(max(order_timestamp), timestamp('1900-01-01'))
    from {{ this }}
)
{% endif %}