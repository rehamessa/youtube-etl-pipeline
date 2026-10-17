import logging

from airflow.operators.bash import BashOperator

logger = logging.getLogger(__name__)

SODA_PATH = "/opt/airflow/include/soda"
DATASOURCE = "pg_datasource"


def yt_elt_data_quality(schema):
    try:
        # Runs the same soda scan command we tested manually, for the given schema.
        # SCHEMA is set as an env variable for configuration.yml and passed with -v as well.
        task = BashOperator(
            task_id=f"soda_test_{schema}",
            bash_command=(
                f"SCHEMA={schema} soda scan -d {DATASOURCE} "
                f"-c {SODA_PATH}/configuration.yml "
                f"-v SCHEMA={schema} "
                f"{SODA_PATH}/checks.yml"
            ),
        )
        return task

    except Exception as e:
        logger.error(f"Error running data quality check for schema: {schema}")
        raise e