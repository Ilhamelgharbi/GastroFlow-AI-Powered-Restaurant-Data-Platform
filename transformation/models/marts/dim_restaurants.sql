-- Exposes cleaned restaurant attributes for reporting and fact joins.
-- The staged restaurant ID remains the dimension's stable join key.
select
    restaurant_id,
    restaurant_name,
    city,
    cuisine,
    rating,
    rating_count,
    cost_for_two
from {{ ref('stg_restaurants') }}