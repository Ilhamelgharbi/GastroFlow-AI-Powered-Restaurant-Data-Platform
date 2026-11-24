-- Cast the review's restaurant ID for a type-safe join; LEFT JOIN keeps unmatched reviews.
select
    r.review_id,
    r.order_id,
    safe_cast(r.user_id as int64) as customer_id,
    cast(r.restaurant_id as string) as restaurant_id,
    safe_cast(r.rating as int64) as rating,
    cast(r.comment as string) as comment,
    safe_cast(r.review_date as date) as review_date,
    res.city as city
from {{ source('raw', 'reviews') }} r
left join {{ ref('stg_restaurants') }} res
    on safe_cast(r.restaurant_id as int64) = res.restaurant_id
-- Keep the existing rule that excludes reviews with no comment.
where r.comment is not null