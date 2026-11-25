-- Convert IDs and prices to numeric types; SAFE_CAST returns NULL for invalid source text.
select
    safe_cast(menu_id as int64) as menu_id,
    safe_cast(r_id as int64) as restaurant_id,
    f_id,
    cuisine,
    round(safe_cast(price as numeric), 2) as price
from {{ source('raw', 'menu') }}
where safe_cast(r_id as int64) is not null
    and round(safe_cast(price as numeric), 2) > 0