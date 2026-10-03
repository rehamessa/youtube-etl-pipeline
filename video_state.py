
import requests
import json
import os
from dotenv import load_dotenv

load_dotenv(dotenv_path="./.env")

api_key=os.getenv("api_key")
channel_handled="MrBeast"

def get_playlist_id():

    try:

        url=f'https://youtube.googleapis.com/youtube/v3/channels?part=contentDetails&forHandle={channel_handled}&key={api_key}'

        response=requests.get(url)

        response.raise_for_status()
        

        data=response.json()
        #print(json.dumps(data,indent=4))

        channel_item=data["items"][0]
        channel_playlistid = channel_item["contentDetails"]["relatedPlaylists"]["uploads"]
        print(channel_playlistid)

        return channel_playlistid

    except requests.exceptions.RequestException as e:
        raise e
    


playlist_id=get_playlist_id()

def get_video_ids(playlist_id):

    video_ids = []
    page_token = None

    base_url = f"https://youtube.googleapis.com/youtube/v3/playlistItems?part=contentDetails&maxResults=50&playlistId={playlist_id}&key={api_key}"

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

def extract_video_data(video_ids):
    extract_data = []

    def batch_list(video_id_list, batch_size):
        for i in range(0, len(video_id_list), batch_size):
            yield video_id_list[i:i + batch_size]

    try:
        for batch in batch_list(video_ids, 50):
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


if __name__ == "__main__":
    get_playlist_id()
    video_ids=get_video_ids(playlist_id)
    print(extract_video_data(video_ids))