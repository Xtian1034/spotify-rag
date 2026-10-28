import sqlite3

from config import DB_PATH

MIN_MS_PLAYED = 30_000 #plays shorter than 30s count as skips
SOURCE = "extended"

GRANULARITY_SQL = {
    "month": "substr(played_at, 1, 7)",
    "weekday": "strftime('%w', played_at)", #0 = Sunday
    "hour": "strftime('%H', played_at)", #UTC
}

def _connect():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn

def _where(start=None, end=None, artist=None, track=None):
    """WHERE clause and its aprams from optional filters. 
    Start/end dates are inclusive dates like 2025-06-01"""
    clauses = ["source = ?", "ms_played >= ?"]
    params = [SOURCE, MIN_MS_PLAYED]
    if start:
        clauses.append("played_at >= ?")
        params.append(start)
    if end:
        clauses.append("played_at < date(?, '+1 day')")
        params.append(end)
    if artist:
        clauses.append("artist_name = ? COLLATE NOCASE")
        params.append(artist)
    if track:
        clauses.append("track_name = ? COLLATE NOCASE")
        params.append(track)
    return "WHERE " + " AND ".join(clauses), params


def _query(sql, params):
    with _connect() as conn:
        return [dict(row) for row in conn.execute(sql, params)]


def top_artists(start=None, end=None, limit=10):
    where, params = _where(start, end)
    sql = f"""
        SELECT artist_name,
                COUNT(*) AS plays,
                ROUND(SUM(ms_played) / 3600000.0, 1) AS hours
        FROM plays {where}
        GROUP BY artist_name
        ORDER BY hours DESC
        LIMIT ?
    """
    return _query(sql, params + [limit])


def top_tracks(start=None, end=None, limit=10, artist=None):
    where, params = _where(start, end, artist)
    sql = f"""
        SELECT track_name, artist_name,
                COUNT(*) AS plays,
                ROUND(SUM(ms_played) / 3600000.0, 1) AS hours
        FROM plays {where}
        GROUP BY track_name, artist_name
        ORDER BY plays DESC
        LIMIT ?
    """
    return _query(sql, params + [limit])


def listening_time(start=None, end=None, artist=None, track=None):
    where, params = _where(start, end, artist, track)
    sql = f"""
        SELECT COUNT(*) AS plays,
                ROUND(COALESCE(SUM(ms_played), 0) / 3600000.0, 1) AS hours,
                MIN(played_at) AS first_played,
                MAX(played_at) AS last_played
        FROM plays {where}
    """
    return _query(sql, params)[0]


def plays_over_time(granularity="month", start=None, end=None, artist=None):
    if granularity not in GRANULARITY_SQL:
        raise ValueError(f"granularity must be one of {list(GRANULARITY_SQL)}")
    bucket = GRANULARITY_SQL[granularity]
    where, params = _where(start, end, artist)
    sql = f"""
        SELECT {bucket} AS period,
                COUNT(*) AS plays,
                ROUND(SUM(ms_played) / 3600000.0, 1) AS hours
        FROM plays {where}
        GROUP BY period
        ORDER BY period
    """
    return _query(sql, params)

def search_artists(query, limit=10):
    sql = """
        SELECT artist_name, COUNT(*) AS plays
        FROM plays
        WHERE source = ? AND artist_name LIKE ?
        GROUP BY artist_name
        ORDER BY plays DESC
        LIMIT ?
    """
    return _query(sql, [SOURCE, f"%{query}%", limit])




