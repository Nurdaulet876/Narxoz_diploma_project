WITH student_activity AS (
    SELECT 
        user_id,
        SUM(view_score) AS total_clicks,
        COUNT(DISTINCT asset_code) AS unique_materials_viewed
    FROM asset_user_accesses
    WHERE context_type = 'Course' 
      AND context_id = 1
    GROUP BY user_id
),
student_grades AS (
    SELECT 
        s.user_id,
        COUNT(s.id) FILTER (WHERE s.submitted_at IS NOT NULL) AS submitted_assignments_count,
        SUM(s.score) AS total_score,
        AVG(s.score) AS average_score
    FROM submissions s
    JOIN assignments a ON s.assignment_id = a.id
    WHERE a.context_type = 'Course' 
      AND a.context_id = 1
      AND s.workflow_state != 'deleted'
    GROUP BY s.user_id
)
SELECT 
    u.id AS student_id,
    u.sortable_name AS student_name,
    COALESCE(e.total_activity_time, 0) AS total_time_seconds,
    COALESCE(act.total_clicks, 0) AS total_clicks,
    COALESCE(act.unique_materials_viewed, 0) AS unique_materials_viewed,
    COALESCE(gr.submitted_assignments_count, 0) AS submitted_assignments_count,
    COALESCE(gr.total_score, 0) AS total_score,
    COALESCE(gr.average_score, 0) AS average_score
FROM users u
JOIN enrollments e ON u.id = e.user_id 
    AND e.type = 'StudentEnrollment' 
    AND e.workflow_state = 'active'
    AND e.course_id = 1
LEFT JOIN student_activity act ON u.id = act.user_id
LEFT JOIN student_grades gr ON u.id = gr.user_id
ORDER BY total_score DESC;


SELECT 
	user_id,
	SUM(view_score) AS total_clicks,
	COUNT(DISTINCT asset_code) AS unique_materials_viewed
FROM asset_user_accesses
WHERE context_type = 'Course' 
  AND context_id = 1
GROUP BY user_id;


SELECT 
	s.user_id,
	COUNT(s.id) FILTER (WHERE s.submitted_at IS NOT NULL) AS submitted_assignments_count,
	SUM(s.score) AS total_score,
	AVG(s.score) AS average_score
FROM submissions s
JOIN assignments a ON s.assignment_id = a.id
WHERE a.context_type = 'Course' 
  AND a.context_id = 1
  AND s.workflow_state != 'deleted'
GROUP BY s.user_id;