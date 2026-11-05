"""SQLite-backed local library of downloaded media."""
from __future__ import annotations

import os
import sqlite3
import time
from typing import Any, Dict, List, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'library.db')


def _conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA journal_mode=WAL')
    return c


def init_db() -> None:
    c = _conn()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS library (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT,
            source_url TEXT NOT NULL,
            title TEXT,
            uploader TEXT,
            duration INTEGER,
            filepath TEXT NOT NULL UNIQUE,
            file_size INTEGER,
            file_hash TEXT,
            resolution TEXT,
            container TEXT,
            downloaded_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_played TEXT,
            play_count INTEGER DEFAULT 0,
            is_favorite INTEGER DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_library_source ON library(source_url);
        CREATE INDEX IF NOT EXISTS idx_library_favorite ON library(is_favorite);
    ''')
    c.commit()
    c.close()


def add_item(item: Dict[str, Any]) -> int:
    c = _conn()
    cur = c.execute('''
        INSERT INTO library (job_id, source_url, title, uploader, duration, filepath,
                             file_size, file_hash, resolution, container, downloaded_at)
        VALUES (:job_id, :source_url, :title, :uploader, :duration, :filepath,
                :file_size, :file_hash, :resolution, :container, :downloaded_at)
    ''', {
        'job_id': item.get('job_id'),
        'source_url': item.get('source_url'),
        'title': item.get('title'),
        'uploader': item.get('uploader'),
        'duration': item.get('duration'),
        'filepath': item.get('filepath'),
        'file_size': item.get('file_size'),
        'file_hash': item.get('file_hash'),
        'resolution': item.get('resolution'),
        'container': item.get('container'),
        'downloaded_at': item.get('downloaded_at', time.strftime('%Y-%m-%d %H:%M:%S')),
    })
    c.commit()
    item_id = cur.lastrowid
    c.close()
    return item_id


def list_items(query: Optional[str] = None, favorite_only: bool = False) -> List[Dict[str, Any]]:
    c = _conn()
    sql = 'SELECT * FROM library WHERE 1=1'
    params: Dict[str, Any] = {}
    if query:
        sql += ' AND (title LIKE :q OR uploader LIKE :q OR source_url LIKE :q)'
        params['q'] = f'%{query}%'
    if favorite_only:
        sql += ' AND is_favorite = 1'
    sql += ' ORDER BY downloaded_at DESC'
    rows = c.execute(sql, params).fetchall()
    c.close()
    return [dict(r) for r in rows]


def get_item(item_id: int) -> Optional[Dict[str, Any]]:
    c = _conn()
    row = c.execute('SELECT * FROM library WHERE id = :id', {'id': item_id}).fetchone()
    c.close()
    return dict(row) if row else None


def delete_item(item_id: int, delete_file: bool = False) -> bool:
    c = _conn()
    row = c.execute('SELECT filepath FROM library WHERE id = :id', {'id': item_id}).fetchone()
    if not row:
        c.close()
        return False
    c.execute('DELETE FROM library WHERE id = :id', {'id': item_id})
    c.commit()
    c.close()
    if delete_file and row['filepath'] and os.path.exists(row['filepath']):
        try:
            os.remove(row['filepath'])
        except OSError:
            pass
    return True


def set_favorite(item_id: int, favorite: bool) -> bool:
    c = _conn()
    cur = c.execute(
        'UPDATE library SET is_favorite = :fav WHERE id = :id',
        {'fav': 1 if favorite else 0, 'id': item_id},
    )
    c.commit()
    changed = cur.rowcount > 0
    c.close()
    return changed


def increment_play(item_id: int) -> None:
    c = _conn()
    c.execute('UPDATE library SET play_count = play_count + 1, last_played = :ts WHERE id = :id',
              {'ts': time.strftime('%Y-%m-%d %H:%M:%S'), 'id': item_id})
    c.commit()
    c.close()
