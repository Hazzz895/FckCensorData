import json
import os
from dotenv import load_dotenv
from git import Repo

load_dotenv()
yandex_music_token = os.getenv("API_TOKEN")

from yandex_music import Client
client = (Client(yandex_music_token) if yandex_music_token else Client()).init()

with open('list.json', 'r') as f:
    data = json.loads(f.read())

def start_appending(id, track_name = None):

    if not track_name:
        print("Fetching track info...")
        track_info = client.tracks([id])[0]
        track_name = f'{track_info.title} - {(", ".join(track_info.artistsName()))}'
        print(f'Track name: {track_name}')
    url = input("Track URL: ")

    repo = Repo('.')
    should_download = True
    if (url):
        if not url.startswith('http'):
            import shutil
            shutil.copy(url, f'tracks/{id}')
            print(f'File copied to tracks/{id}')
        else:
            should_download = input("Download track? (y/n): ").lower() == 'y'
            if should_download:
                import yt_dlp
                def download_sound(url):
                    ydl_opts = {
                        'format': 'bestaudio/best',
                        'outtmpl': f'tracks/{id}',
                    }
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl: # type: ignore
                        ydl.download([url])

                download_sound(url)

    data['tracks'][id] = f'https://raw.githubusercontent.com/Hazzz895/FckCensorData/refs/heads/main/tracks/{id}' if should_download else url

    with open('list.json', 'w') as f:
        json.dump(data, f, indent=4)
        
    with open('README.md', 'a', encoding='utf-8') as f:
        f.write(f'\n- [{track_name}](https://music.yandex.ru/track/{id})')

    repo.index.add(['list.json', f'tracks/{id}', "README.md"])
    repo.index.commit(f"add track «{track_name}»")
    print(f'Successfully added track {track_name}\n')
    
supabase_secret_token = os.getenv("SUPABASE_SECRET_TOKEN")
if supabase_secret_token:
    import requests
    response = requests.get("https://pzomqvgckpgkshxhpite.supabase.co/rest/v1/reported_tracks?select=*", headers = {
        "apikey": supabase_secret_token,
        "Authorization": f"Bearer {supabase_secret_token}",
        "Content-Type": "application/json"
    });
    reports = response.json()
    
    with open('rejected_tracks.dev.json', 'r') as f:
        rejected_tracks = json.loads(f.read())
    
    reports = [report for report in reports if str(report["track_id"]) not in data["tracks"] and not report["track_id"] in rejected_tracks]
    
    for report in reports:
        import datetime
        print(f'== {len(reports)} unreviewed tracks remaining ==')
        id = report["track_id"]
        track_info = client.tracks([id])[0]
        track_name = f'{track_info.title} - {(", ".join(track_info.artistsName()))}'
        print(f'Track name: {track_name}')
        print(f' - https://music.yandex.ru/track/{id}\n - reported at {datetime.datetime.fromisoformat(report["created_at"])}')
        skip = input(" - should append? ") == ""
        if skip:
            rejected_tracks.append(id)
            with open('rejected_tracks.dev.json', 'w') as f:
                json.dump(rejected_tracks, f)
            print("Rejected.")
        else:
            start_appending(id, track_name)
        reports.pop(0)

while True:
    id = input("Yandex Music track ID or URL: ").split('/')[-1].split('?')[0]
    start_appending(id)
    