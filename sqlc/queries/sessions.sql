-- name: InsertSession :one
INSERT INTO sessions (
    id, user_id, started_at, ended_at, duration_sec, booking_made,
    analysis_status, analysis_version, r2_report_path, r2_audio_path,
    analysis_attempts, last_analysis_at, error_message
)
VALUES ($1, $2, $3, $4, $5, $6, 'pending', $7, $8, $9, 0, NULL, NULL)
RETURNING *;

-- name: GetSessionByID :one
SELECT * FROM sessions
WHERE id = $1;

-- name: GetPendingSessions :many
SELECT * FROM sessions
WHERE analysis_status = 'pending'
  AND analysis_attempts < $1
ORDER BY created_at ASC
LIMIT $2;

-- name: UpdateSessionAnalysisStatus :exec
UPDATE sessions
SET analysis_status = $2,
    analysis_attempts = analysis_attempts + 1,
    last_analysis_at = now(),
    error_message = $3
WHERE id = $1;

-- name: MarkSessionAnalysisInProgress :exec
UPDATE sessions
SET analysis_status = 'in_progress',
    analysis_attempts = analysis_attempts + 1,
    last_analysis_at = now()
WHERE id = $1;

-- name: MarkSessionAnalysisCompleted :exec
UPDATE sessions
SET analysis_status = 'completed',
    error_message = NULL
WHERE id = $1;

-- name: MarkSessionAnalysisFailed :exec
UPDATE sessions
SET analysis_status = 'failed',
    error_message = $2
WHERE id = $1;
