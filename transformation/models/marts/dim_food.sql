-- Exposes cleaned food attributes for menu and order-item analysis.
-- This dimension keeps the staging food identifier as its join key.
select
    f_id,
    food_name,
    veg_or_non_veg
from {{ ref('stg_food') }}