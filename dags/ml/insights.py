import logging
from datetime import datetime

from airflow.decorators import task
from psycopg2.extras import execute_values

from datawarehouse.data_utils import get_conn_cursor, close_conn_cursor

logger = logging.getLogger(__name__)

# The ML results go next to the Power BI views
schema = "reporting"


def read_query(sql):
    import pandas as pd
    conn, cur = get_conn_cursor()
    try:
        cur.execute(sql)
        return pd.DataFrame(cur.fetchall())
    finally:
        close_conn_cursor(conn, cur)


def load_videos():
    df = read_query("""
        SELECT "Video_ID", "Video_Title", "Upload_Date", "Duration",
               "Video_Type", "Video_Views"
        FROM core.yt_api;
    """)

    df = df.rename(columns={
        "Video_ID": "video_id",
        "Video_Title": "title",
        "Upload_Date": "upload_date",
        "Duration": "duration",
        "Video_Type": "video_type",
        "Video_Views": "views",
    })

    # Duration is a TIME column -> minutes as a number
    df["duration_minutes"] = df["duration"].apply(
        lambda t: t.hour * 60 + t.minute + t.second / 60
    )
    df["views"] = df["views"].fillna(0).astype(int)

    return df


def to_python(value):
    # psycopg2 can't write numpy types (np.int64, np.float64), so convert them
    return value.item() if hasattr(value, "item") else value


def write_table(table_name, columns_sql, df):
    """Replace the content of reporting.<table_name> with df.

    The table is created once and then emptied on every run (TRUNCATE),
    so Power BI keeps the same table between refreshes.
    """
    conn, cur = get_conn_cursor()
    try:
        cur.execute(f"CREATE SCHEMA IF NOT EXISTS {schema};")
        cur.execute(f"CREATE TABLE IF NOT EXISTS {schema}.{table_name} ({columns_sql});")
        cur.execute(f"TRUNCATE {schema}.{table_name};")

        columns = ", ".join(df.columns)
        values = [tuple(to_python(v) for v in row) for row in df.itertuples(index=False)]
        execute_values(cur, f"INSERT INTO {schema}.{table_name} ({columns}) VALUES %s", values)

        # One commit: the table is never left half empty
        conn.commit()
        logger.info(f"{schema}.{table_name}: {len(df)} rows written")

    except Exception as e:
        conn.rollback()
        logger.error(f"Failed to write {schema}.{table_name}: {e}")
        raise e

    finally:
        close_conn_cursor(conn, cur)


@task
def build_video_topics():
    from ml.features import build_topics
    df = load_videos()

    topic_ids, topics = build_topics(df["title"].tolist())
    df["topic_id"] = topic_ids

    # How each topic performs
    summary = (
        df.groupby("topic_id")["views"]
        .agg(videos="count", median_views="median", avg_views="mean")
        .reset_index()
    )
    topics = topics.merge(summary, on="topic_id")
    topics["median_views"] = topics["median_views"].round().astype(int)
    topics["avg_views"] = topics["avg_views"].round().astype(int)

    write_table(
        "ml_topics",
        """topic_id INT PRIMARY KEY,
           topic_label TEXT,
           top_terms TEXT,
           videos INT,
           median_views BIGINT,
           avg_views BIGINT""",
        topics[["topic_id", "topic_label", "top_terms", "videos", "median_views", "avg_views"]],
    )
    write_table(
        "ml_video_topics",
        """video_id VARCHAR(11) PRIMARY KEY,
           topic_id INT""",
        df[["video_id", "topic_id"]],
    )

    logger.info(f"Built {len(topics)} topics")


@task
def train_success():
    import pandas as pd
    from ml.features import add_features, add_success_label, train_success_model
    df = load_videos()

    # Topics come from the build_video_topics task
    video_topics = read_query(f"SELECT video_id, topic_id FROM {schema}.ml_video_topics;")
    df = df.merge(video_topics, on="video_id", how="left")
    df["topic_id"] = df["topic_id"].fillna(-1).astype(int)

    df = add_success_label(add_features(df))
    predictions, importance, metrics = train_success_model(df)

    write_table(
        "ml_video_predictions",
        """video_id VARCHAR(11) PRIMARY KEY,
           success_probability NUMERIC(6, 4),
           is_success INT""",
        predictions,
    )
    write_table(
        "ml_feature_importance",
        """feature TEXT PRIMARY KEY,
           importance NUMERIC(6, 4)""",
        importance,
    )

    run_at = datetime.now()
    metrics_df = pd.DataFrame(
        [{"metric": name, "value": value, "run_at": run_at} for name, value in metrics.items()]
    )
    write_table(
        "ml_model_metrics",
        """metric TEXT PRIMARY KEY,
           value NUMERIC,
           run_at TIMESTAMP""",
        metrics_df,
    )

    logger.info(f"Success model metrics: {metrics}")


@task
def similar_videos():
    from ml.features import find_similar_videos
    df = load_videos()
    similar = find_similar_videos(df, top_n=5)

    write_table(
        "ml_similar_videos",
        """video_id VARCHAR(11),
           similar_video_id VARCHAR(11),
           similarity NUMERIC(6, 4),
           similar_rank INT,
           PRIMARY KEY (video_id, similar_rank)""",
        similar,
    )
