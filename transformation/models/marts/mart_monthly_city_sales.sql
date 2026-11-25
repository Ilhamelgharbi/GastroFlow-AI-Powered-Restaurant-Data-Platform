-- Aggregates orders and delivered sales by month and city.
-- DATE_TRUNC groups dates into calendar months; SAFE_CAST parses the RAW date and sales.
select
    date_trunc(safe_cast(order_date as date), month) as order_month,
    city,
    count(*) as order_count,
    countif(is_delivered) as delivered_order_count,
    countif(order_status = 'Cancelled') as cancelled_order_count,
    sum(if(is_delivered, safe_cast(sales_amount as numeric), 0)) as delivered_gmv
from {{ ref('fct_orders') }}
where safe_cast(order_date as date) is not null
group by 1, 2
