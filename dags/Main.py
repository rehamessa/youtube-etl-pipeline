from airflow import DAG
import pendulum
from datetime import datetime, timedelta

from api.video_stats import (
    get_playlist_id,
    get_video_ids,
    extract_video_data,
    save_to_json,
)
from datawarehouse.dwh import staging_table, core_table
from dataquality.soda import yt_elt_data_quality

# Local timezone (Egypt)
local_tz = pendulum.timezone("Africa/Cairo")

default_args = {
    "owner": "dataengineers",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "max_active_runs": 1,
    "dagrun_timeout": timedelta(hours=1),
    "start_date": datetime(2026, 1, 1, tzinfo=local_tz),
}

# Schema names used by the data quality DAG
staging_schema = "staging"
core_schema = "core"

# DAG 1: extract data from the YouTube API and save it as JSON
with DAG(
    dag_id="produce_json",
    default_args=default_args,
    description="DAG to produce JSON file with raw data",
    schedule="0 14 * * *",  # Every day at 2 PM
    catchup=False,
) as dag_produce:

    # Define tasks
    playlist_id = get_playlist_id()
    video_ids = get_video_ids(playlist_id)
    extract_data = extract_video_data(video_ids)
    save_to_json_task = save_to_json(extract_data)

    # Task dependencies
    playlist_id >> video_ids >> extract_data >> save_to_json_task


# DAG 2: load the JSON into staging, then transform it into core
with DAG(
    dag_id="update_db",
    default_args=default_args,
    description="DAG to process JSON file and insert data into both staging and core schemas",
    schedule="0 15 * * *",  # Every day at 3 PM, after produce_json
    catchup=False,
) as dag_update:

    # Define tasks
    update_staging = staging_table()
    update_core = core_table()

    # Task dependencies
    update_staging >> update_core


# DAG 3: run Soda data quality checks on both layers
with DAG(
    dag_id="data_quality",
    default_args=default_args,
    description="DAG to check the data quality on both layers in the database",
    schedule="0 16 * * *",  # Every day at 4 PM, after update_db
    catchup=False,
) as dag_quality:

    # Define tasks
    soda_validate_staging = yt_elt_data_quality(staging_schema)
    soda_validate_core = yt_elt_data_quality(core_schema)

    # Task dependencies
    soda_validate_staging >> soda_validate_core