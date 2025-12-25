import sqlite3
from rich.console import Console

# Create a local console for logging errors within this module
console = Console()

class DatabaseManager:
    def __init__(self, db_file):
        self.db_file = db_file
        self.conn = None

    def connect(self):
        if self.conn is None:
            self.conn = sqlite3.connect(self.db_file)
            self.conn.row_factory = sqlite3.Row
            self._migrate()
    
    def _migrate(self):
        c = self.conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS seen_videos
                     (video_id TEXT PRIMARY KEY, title TEXT, seen_date TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS video_metadata
                     (video_id TEXT PRIMARY KEY, duration TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS playlists (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL UNIQUE,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        is_system_list BOOLEAN DEFAULT 0
                     )''')
        c.execute('''CREATE TABLE IF NOT EXISTS videos (
                        video_id TEXT PRIMARY KEY,
                        title TEXT,
                        channel TEXT,
                        url TEXT,
                        duration TEXT,
                        is_shorts BOOLEAN,
                        published_date TEXT,
                        first_seen TEXT DEFAULT CURRENT_TIMESTAMP
                     )''')
        c.execute('''CREATE TABLE IF NOT EXISTS playlist_items (
                        playlist_id INTEGER NOT NULL,
                        video_id TEXT NOT NULL,
                        added_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
                        FOREIGN KEY (video_id) REFERENCES videos(video_id) ON DELETE CASCADE,
                        PRIMARY KEY (playlist_id, video_id)
                     )''')
        c.execute("INSERT OR IGNORE INTO playlists (name, is_system_list) VALUES (?, ?)", ("Watch Later", 1))
        self.conn.commit()

    def execute(self, query, params=()):
        if not self.conn: self.connect()
        try:
            c = self.conn.cursor()
            c.execute(query, params)
            self.conn.commit()
            return c
        except Exception as e:
            console.print(f"DB Error: {e}", style="red")
            return None

    def executemany(self, query, params_list):
        if not self.conn: self.connect()
        try:
            c = self.conn.cursor()
            c.executemany(query, params_list)
            self.conn.commit()
            return c
        except Exception as e:
            console.print(f"DB Error: {e}", style="red")
            return None
            
    def fetchall(self, query, params=()):
        if not self.conn: self.connect()
        try:
            c = self.conn.cursor()
            c.execute(query, params)
            return c.fetchall()
        except Exception as e:
            return []

    def fetchone(self, query, params=()):
        if not self.conn: self.connect()
        try:
            c = self.conn.cursor()
            c.execute(query, params)
            return c.fetchone()
        except Exception as e:
            return None

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
