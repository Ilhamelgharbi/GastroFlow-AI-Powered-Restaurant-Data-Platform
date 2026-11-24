-- Aggregates order volume, delivered revenue, ratings, and delivery time by restaurant.
-- SAFE_CAST converts RAW string measures; IF selects only delivered revenue.
select
    f.restaurant_id,
    r.restaurant_name,
    r.city,
    r.cuisine,
    count(*) as orders,
    sum(if(f.is_delivered, safe_cast(f.sales_amount as numeric), 0)) as revenue,
    round(avg(safe_cast(f.customer_rating as numeric)), 2) as avg_customer_rating,
    round(avg(safe_cast(f.delivery_time_min as numeric)), 1) as avg_delivery_min
from {{ ref('fct_orders') }} f
left join {{ ref('dim_restaurants') }} r
    on safe_cast(f.restaurant_id as int64) = r.restaurant_id
group by 1, 2, 3, 4