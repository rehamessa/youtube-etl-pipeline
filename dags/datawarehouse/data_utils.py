from airflow.providers.postgres.hooks.postgres import PostgresHook
from psycopg2.extras import RealDictCursor


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