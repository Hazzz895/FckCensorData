import json
import os
import threading
import shutil
import datetime
import requests
from dotenv import load_dotenv
from git import Repo
import urllib
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

def start_appending(id, track_name=None, url=None):
    if not track_name:
        print("Fetching track info...")
        track_info = client.tracks([id])[0]
        track_name = f'{track_info.title} - {(", ".join(track_info.artistsName()))}'
        print(f'Track name: {track_name}')
    if not url:
        url = input("Track URL: ")

    repo = Repo('.')
    should_download = True
    if url:
        if not url.startswith('http'):
            shutil.copy(url, f'tracks/{id}')
            print(f'File copied to tracks/{id}')
        else:
            should_download = url.startswith("https://soundcloud.com/") or input("Download from url? (y/n) ") == "y"
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
        f.write(f'\n- [{track_name}](https://music.yandex.ru/track/{id})')

    repo.index.add(['list.json', f'tracks/{id}', "README.md"])
    repo.index.commit(f"add track «{track_name}»")
    print(f'Successfully added track {track_name}\n')
    
if supabase_secret_token:
    SUPABASE_BASE_URL = "https://pzomqvgckpgkshxhpite.supabase.co/rest/v1"
    supabase_headers = {
        "apikey": supabase_secret_token,
        "Authorization": f"Bearer {supabase_secret_token}",
        "Content-Type": "application/json"
    }
    response = requests.get(SUPABASE_BASE_URL + "/reported_tracks?select=*&limit=10000", headers=supabase_headers)
    reports = response.json()
    
    try:
        response = requests.get(SUPABASE_BASE_URL + "/rejected_tracks?select=*&limit=10000", headers=supabase_headers)
        rejected_tracks = [str(x["track_id"]) for x in response.json()]
    except FileNotFoundError:
        rejected_tracks =[]
    
    reports = [report for report in reports if str(report["track_id"]) not in data["tracks"] and str(report["track_id"]) not in rejected_tracks]
    
    with open('ym_tracks_info.dev.json', 'r', encoding='utf-8') as f:
        tracks_info = json.loads(f.read())
    
    known_track_ids = {str(t["id"]) for t in tracks_info}
    unlisted_tracks =[track for track in reports if str(track["track_id"]) not in known_track_ids]
    if len(unlisted_tracks) > 0:
        print(f'Found {len(unlisted_tracks)} unlisted tracks in the library:')
        fetched_tracks = client.tracks([track["track_id"] for track in unlisted_tracks])
        ym =[t.to_dict() for t in fetched_tracks if t is not None]
        
        tracks_info.extend(ym)
        with open('ym_tracks_info.dev.json', 'w', encoding='utf-8') as f:
            json.dump(tracks_info, f, indent=4)
    
    tracks_info_dict = {str(track["id"]): track for track in tracks_info if len(track["albums"]) > 0}
    
    reports.sort(key=lambda report: tracks_info_dict[str(report["track_id"])]["albums"][0]["likes_count"] or 0 if str(report["track_id"]) in tracks_info_dict else 0, reverse=True)
    
    for i, report in enumerate(reports):
        print(f'== {len(reports) - i} unreviewed tracks remaining ==')
        
        id = str(report["track_id"])
        
        if sync_port:
            send_ws({"id": id})
                
        track_info = tracks_info_dict.get(id)
        track_name = f'{track_info["title"]} - {(", ".join([a["name"] for a in track_info["artists"]]))}' if track_info else f'Track ID {id}'
        print(f'Track name: {track_name} ({track_info["albums"][0]["likes_count"]} likes)' if track_info else "Track info not found")
        print(f' - https://music.yandex.ru/track/{id}\n - reported at {datetime.datetime.fromisoformat(report["created_at"])} | REPLACED: {report["replaced"]}')
        print(f' - hitmos fast link: https://rus.hitmoz.org/search?q={urllib.parse.quote(track_name)}') # type: ignore
        dk = input(" - track url ")
        if dk == "":
            rejected_tracks.append(id)
            requests.post(SUPABASE_BASE_URL + "/rejected_tracks", json={"track_id": id}, headers=supabase_headers)
            print("Rejected.")
        elif dk == "skip":
            continue
        elif dk == "manual":
            break
        elif dk == " ":
            downloads_folder = os.path.join(os.path.expanduser("~"), "Downloads")
            list_of_files = os.listdir(downloads_folder)
            list_of_files = [f for f in list_of_files if not f.endswith('.part')]
            latest_file = max(list_of_files, key=lambda x: os.path.getctime(os.path.join(downloads_folder, x)))
            dk = os.path.join(downloads_folder, latest_file)
            print(f'Appending by link: {dk}')
            start_appending(id, track_name, dk)
        else:
            start_appending(id, track_name, dk)

while True:
    user_input = input("Yandex Music track ID or URL: ")
    id = user_input.split('/')[-1].split('?')[0]
    start_appending(id)