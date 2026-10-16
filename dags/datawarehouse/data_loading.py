import json
import logging
from datetime import date

logger = logging.getLogger(__name__)


def load_data():
    # Same path and naming used by save_to_json in api/video_stats.py
    file_path = f"./data/YT_data_{date.today()}.json"

    try:
        logger.info(f"Processing file: YT_data_{date.today()}")

        with open(file_path, "r", encoding="utf-8") as raw_data:
            # Loads the whole file into memory: fine for small files,
            # large files (GBs) should be streamed instead (e.g. ijson)
            data = json.load(raw_data)

        return data

    except FileNotFoundError:
        logger.error(f"File not found: {file_path}")
        raise
    except json.JSONDecodeError:
        logger.error(f"Invalid JSON in file: {file_path}")
        raise