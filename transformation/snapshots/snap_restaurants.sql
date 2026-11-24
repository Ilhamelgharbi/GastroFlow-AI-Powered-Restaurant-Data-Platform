{% snapshot snap_restaurants %}
{{
    config(
        unique_key='restaurant_id',
        strategy='check',
        check_cols=[
            'restaurant_name',
            'city',
            'rating',
            'rating_count',
            'cost_for_two',
            'cuisine',
            'license_no'
        ]
    )
}}

-- Check these business fields because the source has no reliable updated_at column.
select
    restaurant_id,
    restaurant_name,
    city,
    rating,
    rating_count,
    cost_for_two,
    cuisine,
    license_no
from {{ ref('stg_restaurants') }}

{% endsnapshot %}
