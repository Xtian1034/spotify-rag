"""Fetch top Last.fm tags for frequently played artists into artist_tags.

Run from backend/:  python -m ingest.enrich_lastfm

Safe to re-run and to interrupt: each artist is committed as it's fetched,
and artists already in lastfm_fetched are skipped.
"""
import time
from datetime import datetime, timezone

import requests

from config import LASTFM_API_KEY
from ingest.db import connect, init_db

API_URL = "https://ws.audioscrobbler.com/2.0/"
MIN_LISTENS = 5          # only enrich artists with at least this many real listens
MIN_MS_PLAYED = 30_000   # same "real listen" rule as app/tools.py
MAX_TAGS = 5             # keep the top N tags per artist
MIN_TAG_WEIGHT = 10      # drop tags Last.fm scores below this (0-100)
REQUEST_DELAY = 0.25     # seconds between calls, ~4 requests/sec
IGNORE_TAGS = {"seen live", "favorites", "favourite", "favorite", "albums i own"}

# Last.fm error codes: 6 = not found, 29 = rate limit exceeded
ERROR_NOT_FOUND = 6
ERROR_RATE_LIMIT = 29

ARTISTS_TO_FETCH_SQL = """
SELECT artist_name, COUNT(*) AS listens
FROM plays
WHERE source = 'extended'
  AND ms_played >= ?
  AND artist_name NOT IN (SELECT artist_name FROM lastfm_fetched)
GROUP BY artist_name
HAVING listens >= ?
ORDER BY listens DESC
"""


def fetch_top_tags(artist):
    """Return (status, [(tag, weight), ...]) for one artist."""
    params = {
        "method": "artist.gettoptags",
        "artist": artist,
        "autocorrect": 1,  # let Last.fm fix small spelling differences
        "api_key": LASTFM_API_KEY,
        "format": "json",
    }
    while True:
        data = requests.get(API_URL, params=params, timeout=10).json()
        if data.get("error") == ERROR_RATE_LIMIT:
            print("  rate limited, waiting 30s")
            time.sleep(30)
            continue
        break

    if data.get("error") == ERROR_NOT_FOUND:
        return "not_found", []
    if "error" in data:
        raise RuntimeError(f"Last.fm error {data['error']}: {data.get('message')}")

    tags = data.get("toptags", {}).get("tag", [])
    if isinstance(tags, dict):
        # Last.fm's JSON returns a single tag as an object instead of a list
        tags = [tags]

    kept, seen = [], set()
    for t in tags:
        name = t["name"].strip().lower().replace("-", " ")  # 'hip-hop' -> 'hip hop'
        weight = int(t["count"])
        if weight < MIN_TAG_WEIGHT or name in IGNORE_TAGS or name in seen:
            continue
        seen.add(name)
        kept.append((name, weight))
        if len(kept) == MAX_TAGS:
            break
    return ("ok" if kept else "no_tags"), kept


def main():
    if not LASTFM_API_KEY:
        raise SystemExit("LASTFM_API_KEY is not set in backend/.env")

    conn = connect()
    init_db(conn)
    artists = conn.execute(ARTISTS_TO_FETCH_SQL, (MIN_MS_PLAYED, MIN_LISTENS)).fetchall()
    print(f"{len(artists)} artists to fetch")

    counts = {"ok": 0, "not_found": 0, "no_tags": 0}
    for i, row in enumerate(artists, start=1):
        artist = row["artist_name"]
        status, tags = fetch_top_tags(artist)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with conn:  # one transaction per artist, so an interrupt keeps progress
            conn.executemany(
                "INSERT OR IGNORE INTO artist_tags (artist_name, tag, weight) VALUES (?, ?, ?)",
                [(artist, tag, weight) for tag, weight in tags],
            )
            conn.execute(
                "INSERT OR REPLACE INTO lastfm_fetched (artist_name, status, fetched_at) VALUES (?, ?, ?)",
                (artist, status, now),
            )
        counts[status] += 1
        print(f"[{i}/{len(artists)}] {artist}: {', '.join(t for t, _ in tags) or status}")
        time.sleep(REQUEST_DELAY)

    print(f"done: {counts}")
    conn.close()


if __name__ == "__main__":
    main()