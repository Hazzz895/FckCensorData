FCK_CENSOR_URL = "https://github.com/Hazzz895/FckCensor"
HEADER = f'# Список автоматических подмен аддона <a href="{FCK_CENSOR_URL}">FckCensor</a>'
SUB_HEADER_PREFIX = 'Автоматически подменяемые '

from dataclasses import dataclass
import json, os
from core import get_albums, get_artists, get_tracks

if os.path.exists("README.md"):
    os.remove("README.md")

@dataclass
class Row:
    image_url: str | None
    name: str | None
    artists: str | None
    id: str

class Table:
    def __init__(self, name, kind):
        self.name = name
        self.kind = kind
        self.rows = []

class List:
    def __init__(self):
        self.tracks = Table("треки", 'track')
        self.artists = Table("исполнители", 'artist')
        self.albums = Table("альбомы", 'album')


def build_list(list_json):
    result = List()
    kinds = ("tracks", "artists", "albums")
    entities_by_kind = {}
    supplemental_ids = {"tracks": [], "artists": []}
    supplemental_id_sets = {"tracks": set(), "artists": set()}

    def add_supplemental_id(kind, entity_id):
        entity_id = str(entity_id)
        if entity_id not in supplemental_id_sets[kind]:
            supplemental_id_sets[kind].add(entity_id)
            supplemental_ids[kind].append(entity_id)

    for source in list_json["sources"]:
        for artist_id in (source.get("artistsInsertions") or {}):
            add_supplemental_id("artists", artist_id)

        for storage in source.get("tracksStorages") or []:
            for track_id in storage.get("trackIds", []):
                add_supplemental_id(
                    "tracks",
                    track_id["id"] if isinstance(track_id, dict) else track_id,
                )
            for track_id in (storage.get("tracks") or {}):
                add_supplemental_id("tracks", track_id)

    def make_row(kind, entity_id, spoof, entity, album_spoofs=None):
        spoof = dict(spoof)
        if kind == "tracks":
            for album in getattr(entity, "albums", None) or []:
                album_id = album.get("id") if isinstance(album, dict) else getattr(album, "id", None)
                album_spoof = (album_spoofs or {}).get(str(album_id), {})
                if "coverUri" not in spoof and "coverUri" in album_spoof:
                    spoof["coverUri"] = album_spoof["coverUri"]

                censor_spoof = album_spoof.get("__fckCensor") or {}
                if (
                    "artists" not in spoof
                    and censor_spoof.get("replaceArtistsInAlbumVolumes")
                    and "artists" in album_spoof
                ):
                    spoof["artists"] = album_spoof["artists"]

        if "coverUri" in spoof:
            image_url = spoof["coverUri"]
        elif kind == "artists":
            cover = getattr(entity, "cover", None)
            image_url = getattr(cover, "uri", None)
        else:
            image_url = getattr(entity, "cover_uri", None)

        name_field = "name" if kind == "artists" else "title"
        name = spoof[name_field] if name_field in spoof else getattr(entity, name_field, None)
        if image_url is None:
            image_url = "https://github.com/user-attachments/assets/668fa0fc-c590-40c6-ad2d-a5420a2c1ced"
        else:
            image_url = "https://" + image_url.replace('%%', '100x100')

        if "artists" in spoof:
            artists = spoof["artists"]
        elif kind == "artists":
            artists = None
        else:
            artists = getattr(entity, "artists", entity["artists"])

        return Row(image_url, name, artists, entity_id)

    for kind in kinds:
        ids = tuple(dict.fromkeys(
            [
                str(entity_id)
                for source in list_json["sources"]
                for entity_id in source.get(kind, {})
            ] + supplemental_ids.get(kind, [])
        ))
        entities = (get_tracks if kind == "tracks" else get_artists if kind == "artists" else get_albums)(*ids)
        entities_by_kind[kind] = {
            str(entity.id): entity
            for entity in entities
            if entity is not None
        }

    for source in list_json["sources"]:
        for kind in kinds:
            table = getattr(result, kind)
            for entity_id, spoof in source.get(kind, {}).items():
                entity_id = str(entity_id)
                entity = entities_by_kind[kind].get(entity_id)
                if entity is None:
                    raise ValueError(f"Yandex Music did not return {kind} {entity_id}")

                table.rows.append(make_row(
                    kind,
                    entity_id,
                    spoof,
                    entity,
                    source.get("albums", {}),
                ))

    supplemental_sources = {}
    for source in list_json["sources"]:
        for storage in source.get("tracksStorages") or []:
            storage_ids = [
                track_id["id"] if isinstance(track_id, dict) else track_id
                for track_id in storage.get("trackIds", [])
            ]
            storage_ids.extend((storage.get("tracks") or {}).keys())
            for track_id in storage_ids:
                supplemental_sources.setdefault(str(track_id), source)

    for kind, entity_ids in supplemental_ids.items():
        table = getattr(result, kind)
        existing_ids = {row.id for row in table.rows}
        for entity_id in entity_ids:
            if entity_id in existing_ids:
                continue

            entity = entities_by_kind[kind].get(entity_id)
            if entity is None:
                raise ValueError(f"Yandex Music did not return {kind} {entity_id}")

            source = supplemental_sources.get(entity_id, {})
            table.rows.append(make_row(
                kind,
                entity_id,
                source.get(kind, {}).get(entity_id, {}),
                entity,
                source.get("albums", {}),
            ))
            existing_ids.add(entity_id)

    return result


with open("list_v2.json", "r", encoding="utf-8") as list_file:
    list_json = json.load(list_file)

list = build_list(list_json)

readme = open("README.md", "w", encoding="utf-8")

readme.write(HEADER)

for table in (list.tracks, list.artists, list.albums):
    import re
    header = SUB_HEADER_PREFIX + table.name
    anchor = re.sub(r'[^\w\-]', '', header.lower().replace(' ', '-'))
    readme.write(f"\n- [{header}](#{anchor})")

for table in (list.tracks, list.artists, list.albums):
    readme.write("\n\n## " + SUB_HEADER_PREFIX + table.name + "\n\n<table>\n\t<tbody>\n")
    for row in table.rows:
        readme.write("\t\t<tr>\n\t\t\t<td>\n\t\t\t\t")
        readme.write(f'<img width="40px" height="40px" src="{row.image_url}" alt="{row.name}">')
        readme.write('\n\t\t\t</td>\n\t\t\t<td>\n\t\t\t\t')
        readme.write(f'<a href="https://music.yandex.ru/{table.kind}/{row.id}">{row.name}</a>')
        readme.write('\n\t\t\t</td>')
        if row.artists:
            readme.write('\n\t\t\t<td>\n\t\t\t\t')
            readme.write(", ".join([f'<a href="https://music.yandex.ru/artist/{getattr(x, "id", x["id"])}">{getattr(x, "name", x["name"])}</a>' for x in row.artists]))
            readme.write('\n\t\t\t</td>')
        readme.write('\n\t\t</tr>\n')
    readme.write("\t</tbody>\n</table>\n\n")