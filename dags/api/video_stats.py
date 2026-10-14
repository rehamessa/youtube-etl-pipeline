import requests
import json
from datetime import date

from airflow.decorators import task
from airflow.models import Variable


api_key = Variable.get("API_KEY")
channel_handled = Variable.get("CHANNEL_HANDLE")
maxResults = 50


@task
def get_playlist_id():

    try:

        url = f'https://youtube.googleapis.com/youtube/v3/channels?part=contentDetails&forHandle={channel_handled}&key={api_key}'

        response = requests.get(url)

        response.raise_for_status()

        data = response.json()
        # print(json.dumps(data, indent=4))

        channel_item = data["items"][0]
        channel_playlistid = channel_item["contentDetails"]["relatedPlaylists"]["uploads"]
        print(channel_playlistid)

        return channel_playlistid

    except requests.exceptions.RequestException as e:
        raise e


@task
def get_video_ids(playlist_id):

    video_ids = []
    page_token = None

    base_url = f"https://youtube.googleapis.com/youtube/v3/playlistItems?part=contentDetails&maxResults={maxResults}&playlistId={playlist_id}&key={api_key}"

    try:
        while True:
            url = base_url
            if page_token:
                url += f"&pageToken={page_token}"
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()

            for item in data.get("items", []):
                video_id = item['contentDetails']['videoId']
                video_ids.append(video_id)

            page_token = data.get("nextPageToken")

            if not page_token:
                break

    except requests.exceptions.RequestException as e:
        raise e

    return video_ids


@task
def extract_video_data(video_ids):
    extract_data = []

    def batch_list(video_id_list, batch_size):
        for i in range(0, len(video_id_list), batch_size):
            yield video_id_list[i:i + batch_size]

    try:
        for batch in batch_list(video_ids, maxResults):
            video_id_str = ",".join(batch)

            url = f"https://youtube.googleapis.com/youtube/v3/videos?part=contentDetails&part=statistics&part=snippet&id={video_id_str}&key={api_key}"
            response = requests.get(url)
            response.raise_for_status()

            data = response.json()

            for item in data.get('items', []):
                video_id = item['id']
                snippet = item['snippet']
                contentDetails = item["contentDetails"]
                statistics = item['statistics']

                video_data = {
                    'video_id': video_id,
                    'title': snippet['title'],
                    'publishedAt': snippet['publishedAt'],
                    'duration': contentDetails['duration'],
                    'viewCount': statistics.get('viewCount', None),
                    'likeCount': statistics.get('likeCount', None),
                    'commentCount': statistics.get('commentCount', None)
                }

                extract_data.append(video_data)

        return extract_data

    except requests.exceptions.RequestException as e:
        raise e


@task
def save_to_json(extracted_data):
   
    file_path = f"./data/YT_data_{date.today()}.json"

    with open(file_path, "w", encoding="utf-8") as json_outfile:
        json.dump(extracted_data, json_outfile, indent=4, ensure_ascii=False)