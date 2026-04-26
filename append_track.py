import json
import os
import threading
import shutil
import datetime
import requests
from dotenv import load_dotenv
from git import Repo
import yt_dlp
from yandex_music import Client
from websockets.sync.server import serve

load_dotenv()
yandex_music_token = os.getenv("API_TOKEN")
sync_port = os.getenv("SYNC_PORT")
supabase_secret_token = os.getenv("SUPABASE_SECRET_TOKEN")

client = (Client(yandex_music_token) if yandex_music_token else Client()).init()

with open('list.json', 'r', encoding='utf-8') as f:
    data = json.loads(f.read())

con = None
def run_ws_server(port):
    def handler(ws):
        global con
        con = ws
        while True:
            try:
                ws.recv()
            except:
                break
    with serve(handler, "127.0.0.1", port) as server:
        server.serve_forever()

def send_ws(msg):
    if not con:
        return
    msg_str = json.dumps(msg)
    con.send(msg_str)

if sync_port:
    ws_thread = threading.Thread(target=run_ws_server, args=(int(sync_port),), daemon=True)
    ws_thread.start()

def start_appending(id, track_name=None):
    if not track_name:
        print("Fetching track info...")
        track_info = client.tracks([id])[0]
        track_name = f'{track_info.title} - {(", ".join(track_info.artistsName()))}'
        print(f'Track name: {track_name}')
    url = input("Track URL: ")

    repo = Repo('.')
    should_download = True
    if url:
        if not url.startswith('http'):
            shutil.copy(url, f'tracks/{id}')
            print(f'File copied to tracks/{id}')
        else:
            should_download = True
            if should_download:
                def download_sound(url):
                    ydl_opts = {
                        'format': 'bestaudio/best',
                        'outtmpl': f'tracks/{id}',
                    }
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl: # type: ignore
                        ydl.download([url])

                download_sound(url)

    data['tracks'][id] = f'https://raw.githubusercontent.com/Hazzz895/FckCensorData/refs/heads/main/tracks/{id}' if should_download else url

    with open('list.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
        
    with open('README.md', 'a', encoding='utf-8') as f:
        f.write(f'\n-[{track_name}](https://music.yandex.ru/track/{id})')

    repo.index.add(['list.json', f'tracks/{id}', "README.md"])
    repo.index.commit(f"add track «{track_name}»")
    print(f'Successfully added track {track_name}\n')
    
if supabase_secret_token:
    response = requests.get("https://pzomqvgckpgkshxhpite.supabase.co/rest/v1/reported_tracks?select=*", headers={
        "apikey": supabase_secret_token,
        "Authorization": f"Bearer {supabase_secret_token}",
        "Content-Type": "application/json"
    })
    reports = response.json()
    
    with open('rejected_tracks.dev.json', 'r', encoding='utf-8') as f:
        rejected_tracks = json.loads(f.read())
    
    reports = [report for report in reports if str(report["track_id"]) not in data["tracks"] and report["track_id"] not in rejected_tracks]
    
    for i, report in enumerate(reports):
        print(f'== {len(reports) - i} unreviewed tracks remaining ==')
        id = report["track_id"]
        
        if sync_port:
            send_ws({"id": id})
                
        track_info = client.tracks([id])[0]
        track_name = f'{track_info.title} - {(", ".join(track_info.artistsName()))}'
        print(f'Track name: {track_name}')
        print(f' - https://music.yandex.ru/track/{id}\n - reported at {datetime.datetime.fromisoformat(report["created_at"])} | REPLACED: {report["replaced"]}')
        skip = input(" - should append? ") == ""
        if skip:
            rejected_tracks.append(id)
            with open('rejected_tracks.dev.json', 'w', encoding='utf-8') as f:
                json.dump(rejected_tracks, f)
            print("Rejected.")
        else:
            start_appending(id, track_name)

while True:
    user_input = input("Yandex Music track ID or URL: ")
    id = user_input.split('/')[-1].split('?')[0]
    start_appending(id)