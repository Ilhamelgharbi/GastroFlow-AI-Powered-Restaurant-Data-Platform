-- Ranks food items by order volume and sales.
-- SAFE_CAST handles numeric values that remain strings in the RAW-derived fact.
select
    f.f_id as food_id,
    d.food_name,
    d.veg_or_non_veg,
    count(distinct f.order_id) as order_count,
    sum(safe_cast(f.quantity as int64)) as quantity_sold,
    sum(safe_cast(f.line_amount as numeric)) as sales_amount
from {{ ref('fct_order_items') }} f
left join {{ ref('dim_food') }} d
    on f.f_id = d.f_id
group by 1, 2, 3
