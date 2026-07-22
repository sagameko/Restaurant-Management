-- reviews.rating between 1 and 5 (spec's own example test).
select review_id, rating
from {{ ref('fact_reviews') }}
where rating is not null and rating not between 1 and 5
