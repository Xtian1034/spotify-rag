import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR.parent / "data"
RAW_DIR = DATA_DIR / "raw"
DB_PATH = DATA_DIR / "spotify.db"

class Config:
    DEBUG = os.getenv("FLASK_DEBUG") == "1"