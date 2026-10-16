from airflow.providers.postgres.hooks.postgres import PostgresHook
from psycopg2.extras import RealDictCursor

# Same table name is used in both schemas (staging and core)
table = "yt_api"


def get_conn_cursor():
    # Connection ID comes from AIRFLOW_CONN_POSTGRES_DB_YT_ELT in docker-compose
    hook = PostgresHook(postgres_conn_id="postgres_db_yt_elt", database="elt_db")
    conn = hook.get_conn()
    # RealDictCursor returns query results as dictionaries instead of tuples
    cur = conn.cursor(cursor_factory=RealDictCursor)
    return conn, cur


def close_conn_cursor(conn, cur):
    # Always close the cursor and connection to release resources
    cur.close()
    conn.close()


def create_schema(schema):
    conn, cur = get_conn_cursor()

    # IF NOT EXISTS: only create the schema if it is not already there
    schema_sql = f"CREATE SCHEMA IF NOT EXISTS {schema};"

    cur.execute(schema_sql)
    # Commit is required to save changes to the database
    conn.commit()

    close_conn_cursor(conn, cur)


def create_table(schema):
    conn, cur = get_conn_cursor()

    if schema == "staging":
        # Raw layer: data as it comes from the API
        table_sql = f"""
            CREATE TABLE IF NOT EXISTS {schema}.{table} (
                "Video_ID" VARCHAR(11) PRIMARY KEY NOT NULL,
                "Video_Title" TEXT NOT NULL,
                "Upload_Date" TIMESTAMP NOT NULL,
                "Duration" VARCHAR(20) NOT NULL,
                "Video_Views" INT,
                "Likes_Count" INT,
                "Comments_Count" INT
            );
        """
    else:
        # Refined layer: duration converted to TIME and a new Video_Type column
        table_sql = f"""
            CREATE TABLE IF NOT EXISTS {schema}.{table} (
                "Video_ID" VARCHAR(11) PRIMARY KEY NOT NULL,
                "Video_Title" TEXT NOT NULL,
                "Upload_Date" TIMESTAMP NOT NULL,
                "Duration" TIME NOT NULL,
                "Video_Type" VARCHAR(10) NOT NULL,
                "Video_Views" INT,
                "Likes_Count" INT,
                "Comments_Count" INT
            );
        """

    cur.execute(table_sql)
    conn.commit()

    close_conn_cursor(conn, cur)


def get_video_ids(cur, schema):
    cur.execute(f"""SELECT "Video_ID" FROM {schema}.{table};""")
    # fetchall returns a list of dicts, e.g. [{"Video_ID": "abc"}, {"Video_ID": "xyz"}]
    ids = cur.fetchall()

    # Keep only the values, e.g. ["abc", "xyz"]
    video_ids = [row["Video_ID"] for row in ids]

    return video_ids