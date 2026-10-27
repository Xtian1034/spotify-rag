"""Load StreamingHistory_music_*.json (Account Data export) into the plays table.

Run from backend/:  python -m ingest.load_account_export
"""
import json

from config import RAW_DIR
from ingest.db import connect, init_db

SOURCE = "account_export"

INSERT_SQL = """
INSERT OR IGNORE INTO plays (played_at, artist_name, track_name, ms_played, source)
VALUES (?, ?, ?, ?, ?)
"""


def to_iso_utc(end_time):
    # "2025-10-24 19:33" (UTC per Spotify's docs) -> "2025-10-24T19:33:00Z"
    return end_time.replace(" ", "T") + ":00Z"


def parse_file(path):
    for item in json.loads(path.read_text()):
        yield (
            to_iso_utc(item["endTime"]),
            item["artistName"],
            item["trackName"],
            item["msPlayed"],
            SOURCE,
        )


def main():
    files = sorted(RAW_DIR.glob("StreamingHistory_music_*.json"))
    if not files:
        raise SystemExit(f"No StreamingHistory_music_*.json files in {RAW_DIR}")

    conn = connect()
    init_db(conn)
    with conn:
        for path in files:
            rows = list(parse_file(path))
            before = conn.total_changes
            conn.executemany(INSERT_SQL, rows)
            inserted = conn.total_changes - before
            print(f"{path.name}: {len(rows)} rows read, {inserted} inserted")

    total = conn.execute(
        "SELECT COUNT(*) FROM plays WHERE source = ?", (SOURCE,)
    ).fetchone()[0]
    print(f"plays from {SOURCE}: {total}")
    conn.close()


if __name__ == "__main__":
    main()
