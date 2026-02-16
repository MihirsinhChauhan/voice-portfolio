-- name: InsertAnalysisResult :one
INSERT INTO analysis_results (
    id, session_id, sentiment_score, engagement_score, lead_score,
    intent_label, summary, analysis_version
)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
RETURNING *;

-- name: UpsertAnalysisResult :one
INSERT INTO analysis_results (
    id, session_id, sentiment_score, engagement_score, lead_score,
    intent_label, summary, analysis_version
)
VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
ON CONFLICT (session_id)
DO UPDATE SET
    sentiment_score = EXCLUDED.sentiment_score,
    engagement_score = EXCLUDED.engagement_score,
    lead_score = EXCLUDED.lead_score,
    intent_label = EXCLUDED.intent_label,
    summary = EXCLUDED.summary,
    analysis_version = EXCLUDED.analysis_version
RETURNING *;

-- name: GetAnalysisResultBySessionID :one
SELECT * FROM analysis_results
WHERE session_id = $1;
