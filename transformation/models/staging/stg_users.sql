-- SAFE_CAST turns invalid numeric text into NULL instead of failing the view.
select
    safe_cast(user_id as int64) as customer_id,
    name as customer_name,
    lower(email) as email,
    safe_cast(age as int64) as age,
    gender,
    marital_status,
    occupation,
    monthly_income as income_band,
    educational_qualifications as education,
    safe_cast(family_size as int64) as family_size
from {{ source('raw', 'users') }}
where safe_cast(user_id as int64) is not null