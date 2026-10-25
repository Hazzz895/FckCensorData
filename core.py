import json
import os
from pathlib import Path

from dotenv import load_dotenv
from yandex_music import Album, Artist, Client, Track

load_dotenv()
_token = os.getenv("API_TOKEN")
_client = (Client(_token) if _token else Client()).init()

_cache_path = Path(__file__).with_name("ym_cached_entities.dev.json")
with _cache_path.open("r", encoding="utf-8") as f:
    _cache = json.load(f)


def _get(ids, cache_key, model, net_func):
    cache = _cache[cache_key]
    ids = [str(entity_id) for entity_id in ids]
    uncached_ids = [entity_id for entity_id in ids if entity_id not in cache]
    if uncached_ids:
        entities = net_func(uncached_ids)
        for entity in entities:
            cache[str(entity.id)] = entity.to_dict()
        with _cache_path.open("w", encoding="utf-8") as f:
            json.dump(_cache, f, ensure_ascii=False, indent=4)

    result = []
    for entity_id in ids:
        entity = model.de_json(cache[entity_id], _client)
        if entity is None:
            raise ValueError(f"Could not deserialize cached {cache_key} entity {entity_id}")
        result.append(entity)
    return result


def get_tracks(*tracks_ids):
    return _get(tracks_ids, "tracks", Track, _client.tracks)


def get_albums(*albums_ids):
    return _get(albums_ids, "albums", Album, _client.albums)


def get_artists(*artists_ids):
    return _get(artists_ids, "artists", Artist, _client.artists)
