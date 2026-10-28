"""Load Streaming_History_Audio_*.json (Extended Streaming History) into the plays table.

Run from backend/:  python -m ingest.load_extended
"""

import json

from config import RAW_DIR
from ingest.db import connect, init_db

SOURCE = "extended"
EXTENDED_DIR = RAW_DIR / "extended"

INSERT_SQL = """
INSERT OR IGNORE INTO plays (
    played_at, artist_name, track_name, album_name, track_uri,
    ms_played, reason_end, shuffle, skipped, source
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

def to_bool_int(value):
    # JSON true/false/null -> 1/0/None for SQLite
    return None if value is None else int(value)


def parse_file(path):
    """YIELD (row, None) for music plays and (None, reason) for skipped items"""
    for item in json.loads(path.read_text()):
        track = item["master_metadata_track_name"]
        artist = item["master_metadata_album_artist_name"]
        if track is None or artist is None:
            #podcast episode, audiobook chapter, or a play with missing metadata
            yield None, "non-music"
            continue
        yield (
            item["ts"],  # already ISO 8601 UTC, e.g. "2018-10-05T19:34:38Z"
            artist,
            track,
            item["master_metadata_album_album_name"],
            item["spotify_track_uri"],
            item["ms_played"],
            item["reason_end"],
            to_bool_int(item["shuffle"]),
            to_bool_int(item["skipped"]),
            SOURCE,
        ), None

def main():
    files = sorted(EXTENDED_DIR.glob("Streaming_History_Audio_*.json"))
    if not files:
        raise SystemExit(f"No Streaming_History_Audio*.json files in {EXTENDED_DIR}")

    conn = connect()
    init_db(conn)
    with conn:
        for path in files:
            rows, skipped = [], 0
            for row, reason in parse_file(path):
                if row is None:
                    skipped += 1
                else:
                    rows.append(row)
            before = conn.total_changes
            conn.executemany(INSERT_SQL, rows)
            inserted = conn.total_changes - before
            print(f"{path.name}: {len(rows)} music rows, {inserted} inserted, {skipped} skipped")
    total, first, last = conn.execute(
        "SELECT COUNT(*), MIN(played_at), MAX(played_at) FROM plays WHERE source = ?",
        (SOURCE,),
    ).fetchone()
    print(f"plays from {SOURCE}: {total} ({first} -> {last})")
    conn.close()


if __name__ == "__main__":
    main()