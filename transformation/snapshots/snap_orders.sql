{% snapshot snap_orders %}
{{
    config(
        unique_key='order_id',
        strategy='check',
        check_cols=['order_status', 'sales_amount']
    )
}}

-- order_id identifies each order; check records changes to its status or amount.
select
    order_id,
    order_status,
    sales_amount
from {{ ref('stg_orders') }}

{% endsnapshot %}
