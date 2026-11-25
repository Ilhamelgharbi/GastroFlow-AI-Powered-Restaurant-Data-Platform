-- Summarizes order frequency, delivered sales, and active dates by customer.
-- SAFE_CAST matches RAW string customer IDs to the INT64 customer dimension.
select
    c.customer_id,
    c.customer_name,
    c.age_group,
    count(f.order_id) as order_count,
    countif(f.is_delivered) as delivered_order_count,
    sum(if(f.is_delivered, safe_cast(f.sales_amount as numeric), 0)) as delivered_sales,
    min(f.order_timestamp) as first_order_timestamp,
    max(f.order_timestamp) as last_order_timestamp
from {{ ref('dim_customers') }} c
left join {{ ref('fct_orders') }} f
    on safe_cast(f.customer_id as int64) = c.customer_id
group by 1, 2, 3
