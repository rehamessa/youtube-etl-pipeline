-- Reporting layer for the Power BI dashboard
-- Reads from core.yt_api and exposes clean, ready-to-plot views

CREATE SCHEMA IF NOT EXISTS reporting;

-- One row per video, with extra calculated columns
CREATE OR REPLACE VIEW reporting.video_stats AS
SELECT
    "Video_ID"                                          AS video_id,
    "Video_Title"                                       AS video_title,
    "Upload_Date"                                       AS upload_date,
    "Upload_Date"::date                                 AS upload_day,
    EXTRACT(YEAR FROM "Upload_Date")::int               AS upload_year,
    DATE_TRUNC('month', "Upload_Date")::date            AS upload_month,
    TO_CHAR("Upload_Date", 'FMDay')                     AS upload_weekday,
    "Duration"                                          AS duration,
    ROUND((EXTRACT(EPOCH FROM "Duration") / 60.0)::numeric, 2) AS duration_minutes,
    "Video_Type"                                        AS video_type,
    "Video_Views"                                       AS views,
    "Likes_Count"                                       AS likes,
    "Comments_Count"                                    AS comments,
    -- Engagement rate = (likes + comments) / views, in percent
    CASE
        WHEN "Video_Views" > 0
        THEN ROUND(100.0 * (COALESCE("Likes_Count", 0) + COALESCE("Comments_Count", 0)) / "Video_Views", 2)
    END                                                 AS engagement_rate_pct,
    'https://www.youtube.com/watch?v=' || "Video_ID"    AS video_url
FROM core.yt_api;

-- One row per month: how the channel performs over time
CREATE OR REPLACE VIEW reporting.monthly_summary AS
SELECT
    upload_month,
    COUNT(*)                                                    AS videos,
    SUM(views)                                                  AS total_views,
    ROUND(AVG(views))                                           AS avg_views,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY views)          AS median_views,
    SUM(likes)                                                  AS total_likes,
    SUM(comments)                                               AS total_comments
FROM reporting.video_stats
GROUP BY upload_month;

-- One row per video type: Shorts vs Normal
CREATE OR REPLACE VIEW reporting.type_summary AS
SELECT
    video_type,
    COUNT(*)                                                    AS videos,
    SUM(views)                                                  AS total_views,
    ROUND(AVG(views))                                           AS avg_views,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY views)          AS median_views,
    ROUND(AVG(engagement_rate_pct), 2)                          AS avg_engagement_rate_pct,
    ROUND(AVG(duration_minutes), 2)                             AS avg_duration_minutes
FROM reporting.video_stats
GROUP BY video_type;
