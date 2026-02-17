-- name: GetUserProfileByUserID :one
SELECT * FROM user_profiles
WHERE user_id = $1;

-- name: UpsertUserProfile :one
INSERT INTO user_profiles (
    user_id, company, domain, last_intent_type, booked_before, last_visit_at, created_at
)
VALUES (
    sqlc.arg(user_id),
    sqlc.narg(company),
    sqlc.narg(domain),
    sqlc.narg(last_intent_type),
    COALESCE(sqlc.narg(booked_before), false),
    now(),
    now()
)
ON CONFLICT (user_id)
DO UPDATE SET
  company = COALESCE(EXCLUDED.company, user_profiles.company),
  domain = COALESCE(EXCLUDED.domain, user_profiles.domain),
  last_intent_type = COALESCE(EXCLUDED.last_intent_type, user_profiles.last_intent_type),
  booked_before = COALESCE(EXCLUDED.booked_before, user_profiles.booked_before),
  last_visit_at = now()
RETURNING *;

