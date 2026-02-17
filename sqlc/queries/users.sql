-- name: GetUserByID :one
SELECT * FROM users
WHERE id = $1;

-- name: GetUserByVisitorID :one
SELECT * FROM users
WHERE visitor_id = $1;

-- name: GetUserByEmail :one
SELECT * FROM users
WHERE email = $1;

-- name: UpsertUserByVisitorID :one
INSERT INTO users (id, visitor_id, email, name, created_at, last_seen_at, total_sessions, total_bookings)
VALUES ($1, $2, $3, $4, now(), now(), 0, 0)
ON CONFLICT (visitor_id)
DO UPDATE SET
  email = COALESCE(EXCLUDED.email, users.email),
  name = COALESCE(EXCLUDED.name, users.name),
  last_seen_at = now()
RETURNING *;

-- name: UpsertUserByEmail :one
INSERT INTO users (id, email, name, created_at, last_seen_at, total_sessions, total_bookings)
VALUES ($1, $2, $3, now(), now(), 0, 0)
ON CONFLICT (email)
DO UPDATE SET
  name = COALESCE(EXCLUDED.name, users.name),
  last_seen_at = now()
RETURNING *;

-- name: IncrementUserSessionCount :exec
UPDATE users
SET total_sessions = total_sessions + 1,
    last_seen_at = now()
WHERE id = $1;

-- name: IncrementUserBookingCount :exec
UPDATE users
SET total_bookings = total_bookings + 1
WHERE id = $1;
