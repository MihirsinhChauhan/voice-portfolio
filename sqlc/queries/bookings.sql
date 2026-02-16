-- name: InsertBooking :one
INSERT INTO bookings (id, session_id, user_id, scheduled_time, timezone, status)
VALUES ($1, $2, $3, $4, $5, $6)
RETURNING *;

-- name: GetBookingsBySessionID :many
SELECT * FROM bookings
WHERE session_id = $1;

-- name: GetBookingsByUserID :many
SELECT * FROM bookings
WHERE user_id = $1
ORDER BY scheduled_time DESC;
