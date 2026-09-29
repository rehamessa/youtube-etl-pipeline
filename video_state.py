
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

if __name__ == "__main__":
    get_playlist_id()