import psycopg2
import pytest
import requests


def test_youtube_api_response(airflow_variable):
    api_key = airflow_variable("api_key")
    channel_handle = airflow_variable("channel_handle")

    # Same endpoint used by get_playlist_id
    url = (
        "https://youtube.googleapis.com/youtube/v3/channels"
        f"?part=contentDetails&forHandle={channel_handle}&key={api_key}"
    )

    try:
        response = requests.get(url, timeout=30)
        assert response.status_code == 200

    except requests.RequestException as e:
        pytest.fail(f"Request to YouTube API failed: {e}")


def test_real_postgres_connection(real_postgres_connection):
    cursor = None

    try:
        cursor = real_postgres_connection.cursor()
        cursor.execute("SELECT 1;")
        result = cursor.fetchone()  # Default cursor returns a tuple, e.g. (1,)

        assert result[0] == 1

    except psycopg2.Error as e:
        pytest.fail(f"Database query failed: {e}")

    finally:
        if cursor is not None:
            cursor.close()