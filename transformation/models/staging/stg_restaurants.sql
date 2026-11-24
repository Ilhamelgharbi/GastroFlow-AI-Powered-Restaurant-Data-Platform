-- SAFE_CAST handles invalid numeric text; REGEXP_EXTRACT keeps the city after the last comma.
select
    safe_cast(id as int64) as restaurant_id,
    name as restaurant_name,
    trim(coalesce(regexp_extract(city, r'[^,]+$'), city)) as city,
    safe_cast(nullif(rating, '--') as numeric) as rating,
    safe_cast(regexp_extract(rating_count, r'[0-9]+') as int64) as rating_count,
    safe_cast(regexp_extract(cost, r'[0-9]+') as int64) as cost_for_two,
    cuisine,
    lic_no as license_no
from {{ source('raw', 'restaurants') }}
where safe_cast(id as int64) is not null