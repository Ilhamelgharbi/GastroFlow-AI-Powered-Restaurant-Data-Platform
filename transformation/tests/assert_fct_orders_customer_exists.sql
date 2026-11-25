-- Return fact rows whose customer ID does not match the customer dimension.
{{ config(severity='warn') }}
select f.customer_id
from {{ ref('fct_orders') }} as f
left join {{ ref('dim_customers') }} as d
    on safe_cast(f.customer_id as int64) = d.customer_id
where f.customer_id is not null
    and d.customer_id is null
