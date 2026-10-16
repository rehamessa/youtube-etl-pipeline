import logging

from airflow.decorators import task

from datawarehouse.data_utils import (
    get_conn_cursor,
    close_conn_cursor,
    create_schema,
    create_table,
    get_video_ids,
)
from datawarehouse.data_loading import load_data
from datawarehouse.data_modification import insert_rows, update_rows, delete_rows
from datawarehouse.data_transformation import transform_data

logger = logging.getLogger(__name__)

table = "yt_api"


@task
def staging_table():
    schema = "staging"
    conn, cur = None, None

    try:
        conn, cur = get_conn_cursor()

        # Raw data from today's JSON file
        YT_data = load_data()

        create_schema(schema)
        create_table(schema)

        table_ids = get_video_ids(cur, schema)

        # Upsert: insert new videos, update existing ones
        for row in YT_data:
            if len(table_ids) == 0:
                # First load: table is empty
                insert_rows(cur, conn, schema, row)
            else:
                if row["video_id"] in table_ids:
                    update_rows(cur, conn, schema, row)
                else:
                    insert_rows(cur, conn, schema, row)

        # Delete videos that are in the table but no longer in the API data
        ids_in_json = {row["video_id"] for row in YT_data}
        ids_to_delete = set(table_ids) - ids_in_json

        if ids_to_delete:
            delete_rows(cur, conn, schema, ids_to_delete)

        logger.info(f"{schema} table update completed")

    except Exception as e:
        logger.error(f"An error occurred during the update of {schema} table: {e}")
        raise e

    finally:
        # Runs whether the try block succeeded or failed
        if conn and cur:
            close_conn_cursor(conn, cur)


@task
def core_table():
    schema = "core"
    conn, cur = None, None

    try:
        conn, cur = get_conn_cursor()

        create_schema(schema)
        create_table(schema)

        table_ids = get_video_ids(cur, schema)

        # Video IDs seen in this run, used for the delete logic
        current_video_ids = set()

        # Core reads from staging. Fine for a few hundred rows;
        # very large tables should be processed in batches instead
        cur.execute(f"SELECT * FROM staging.{table};")
        rows = cur.fetchall()

        for row in rows:
            current_video_ids.add(row["Video_ID"])

            transformed_row = transform_data(row)

            if len(table_ids) == 0:
                insert_rows(cur, conn, schema, transformed_row)
            else:
                if transformed_row["Video_ID"] in table_ids:
                    update_rows(cur, conn, schema, transformed_row)
                else:
                    insert_rows(cur, conn, schema, transformed_row)

        ids_to_delete = set(table_ids) - current_video_ids

        if ids_to_delete:
            delete_rows(cur, conn, schema, ids_to_delete)

        logger.info(f"{schema} table update completed")

    except Exception as e:
        logger.error(f"An error occurred during the update of {schema} table: {e}")
        raise e

    finally:
        if conn and cur:
            close_conn_cursor(conn, cur)