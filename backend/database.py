import sqlite3
import json
import os
import time
from typing import Optional, Dict, Any

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "anime_cache.db"))

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database tables for caching and cross-device sync."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Cache for anime details
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS anime_cache (
                anime_id INTEGER PRIMARY KEY,
                title TEXT,
                data TEXT,
                updated_at REAL
            )
        """)

        # Cache for filler lists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS filler_cache (
                slug TEXT PRIMARY KEY,
                data TEXT,
                updated_at REAL
            )
        """)

        # User watch progress & device sync
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS watch_progress (
                sync_code TEXT,
                anime_id INTEGER,
                watched_episodes TEXT,
                updated_at REAL,
                PRIMARY KEY (sync_code, anime_id)
            )
        """)
        conn.commit()

# --- Anime Cache Methods ---
def get_cached_anime(anime_id: int, max_age_days: int = 7) -> Optional[Dict[str, Any]]:
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT data, updated_at FROM anime_cache WHERE anime_id = ?", (anime_id,))
            row = cursor.fetchone()
            if row:
                age = time.time() - row["updated_at"]
                if age < max_age_days * 86400:
                    return json.loads(row["data"])
    except Exception as e:
        print(f"DB Read Error (anime_cache): {e}")
    return None

def set_cached_anime(anime_id: int, title: str, data: Dict[str, Any]):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO anime_cache (anime_id, title, data, updated_at)
                VALUES (?, ?, ?, ?)
            """, (anime_id, title, json.dumps(data), time.time()))
            conn.commit()
    except Exception as e:
        print(f"DB Write Error (anime_cache): {e}")

# --- Filler Cache Methods ---
def get_cached_filler(slug: str, max_age_days: int = 7) -> Optional[Dict[str, Any]]:
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT data, updated_at FROM filler_cache WHERE slug = ?", (slug,))
            row = cursor.fetchone()
            if row:
                age = time.time() - row["updated_at"]
                if age < max_age_days * 86400:
                    return json.loads(row["data"])
    except Exception as e:
        print(f"DB Read Error (filler_cache): {e}")
    return None

def set_cached_filler(slug: str, data: Dict[str, Any]):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO filler_cache (slug, data, updated_at)
                VALUES (?, ?, ?)
            """, (slug, json.dumps(data), time.time()))
            conn.commit()
    except Exception as e:
        print(f"DB Write Error (filler_cache): {e}")

# --- Sync & Progress Methods ---
def save_user_progress(sync_code: str, anime_id: int, episodes: list):
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO watch_progress (sync_code, anime_id, watched_episodes, updated_at)
                VALUES (?, ?, ?, ?)
            """, (sync_code, anime_id, json.dumps(episodes), time.time()))
            conn.commit()
    except Exception as e:
        print(f"DB Error (save_user_progress): {e}")

def get_user_progress(sync_code: str, anime_id: int) -> list:
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT watched_episodes FROM watch_progress 
                WHERE sync_code = ? AND anime_id = ?
            """, (sync_code, anime_id))
            row = cursor.fetchone()
            if row and row["watched_episodes"]:
                return json.loads(row["watched_episodes"])
    except Exception as e:
        print(f"DB Error (get_user_progress): {e}")
    return []

# Initialize on module import
init_db()
