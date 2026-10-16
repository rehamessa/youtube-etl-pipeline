import logging

logger = logging.getLogger(__name__)

# Same table name is used in both schemas (staging and core)
table = "yt_api"


def insert_rows(cur, conn, schema, row):
    try:
        if schema == "staging":
            # Staging reads from the JSON file, so placeholders use the JSON keys
            video_id = "video_id"

            cur.execute(
                f"""INSERT INTO {schema}.{table}
                    ("Video_ID", "Video_Title", "Upload_Date", "Duration",
                     "Video_Views", "Likes_Count", "Comments_Count")
                VALUES
                    (%(video_id)s, %(title)s, %(publishedAt)s, %(duration)s,
                     %(viewCount)s, %(likeCount)s, %(commentCount)s);""",
                row,
            )
        else:
            # Core reads from the staging table, so placeholders use staging column names
            video_id = "Video_ID"

            cur.execute(
                f"""INSERT INTO {schema}.{table}
                    ("Video_ID", "Video_Title", "Upload_Date", "Duration",
                     "Video_Type", "Video_Views", "Likes_Count", "Comments_Count")
                VALUES
                    (%(Video_ID)s, %(Video_Title)s, %(Upload_Date)s, %(Duration)s,
                     %(Video_Type)s, %(Video_Views)s, %(Likes_Count)s, %(Comments_Count)s);""",
                row,
            )

        conn.commit()
        logger.info(f"Inserted row with Video_ID: {row[video_id]}")

    except Exception as e:
        logger.error(f"Error inserting row with Video_ID: {row[video_id]}")
        raise e


def update_rows(cur, conn, schema, row):
    try:
        if schema == "staging":
            # Keys based on the JSON file
            video_id = "video_id"
            upload_date = "publishedAt"
            video_title = "title"
            video_views = "viewCount"
            likes_count = "likeCount"
            comments_count = "commentCount"
        else:
            # Keys based on the staging table columns
            video_id = "Video_ID"
            upload_date = "Upload_Date"
            video_title = "Video_Title"
            video_views = "Video_Views"
            likes_count = "Likes_Count"
            comments_count = "Comments_Count"

        # Only values that can change are updated; ID and upload date identify the video
        cur.execute(
            f"""UPDATE {schema}.{table}
                SET "Video_Title" = %({video_title})s,
                    "Video_Views" = %({video_views})s,
                    "Likes_Count" = %({likes_count})s,
                    "Comments_Count" = %({comments_count})s
                WHERE "Video_ID" = %({video_id})s
                  AND "Upload_Date" = %({upload_date})s;""",
            row,
        )

        conn.commit()
        logger.info(f"Updated row with Video_ID: {row[video_id]}")

    except Exception as e:
        logger.error(f"Error updating row with Video_ID: {row[video_id]}")
        raise e


def delete_rows(cur, conn, schema, ids_to_delete):
    try:
        # Convert ['id1', 'id2'] to the SQL string 'id1','id2'
        ids_to_delete = ",".join(f"'{video_id}'" for video_id in ids_to_delete)

        cur.execute(
            f"""DELETE FROM {schema}.{table}
                WHERE "Video_ID" IN ({ids_to_delete});"""
        )

        conn.commit()
        logger.info(f"Deleted rows with Video_ID: {ids_to_delete}")

    except Exception as e:
        logger.error(f"Error deleting rows with Video_ID: {ids_to_delete}")
        raise e