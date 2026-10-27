CREATE TABLE IF NOT EXISTS plays (
    id           INTEGER PRIMARY KEY,
    played_at    TEXT NOT NULL,     -- ISO 8601 UTC, when the play ended
    artist_name  TEXT NOT NULL,
    track_name   TEXT NOT NULL,
    album_name   TEXT,              -- extended history only
    track_uri    TEXT,              -- extended history only
    ms_played    INTEGER NOT NULL,
    reason_end   TEXT,              -- extended history only
    shuffle      INTEGER,           -- extended history only, 0/1
    skipped      INTEGER,           -- extended history only, 0/1
    source       TEXT NOT NULL,     -- 'account_export' | 'extended' | 'api_poll'
    UNIQUE (played_at, artist_name, track_name, source)
);

CREATE INDEX IF NOT EXISTS idx_plays_played_at ON plays(played_at);
CREATE INDEX IF NOT EXISTS idx_plays_artist ON plays(artist_name);
