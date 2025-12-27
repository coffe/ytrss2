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
                        first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
                        download_path TEXT
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
        
        # Check if download_path exists in videos table (for migration)
        try:
            c.execute("SELECT download_path FROM videos LIMIT 1")
        except sqlite3.OperationalError:
            # Column missing, add it
            console.print("Migrating database: Adding download_path to videos table...", style="yellow")
            try:
                c.execute("ALTER TABLE videos ADD COLUMN download_path TEXT")
            except Exception as e:
                console.print(f"Migration failed: {e}", style="red")

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

    def get_stats_data(self):
        """Fetches raw data for statistics."""
        stats = {}
        
        # 1. Total seen videos
        row = self.fetchone("SELECT COUNT(*) FROM seen_videos")
        stats['total_seen'] = row[0] if row else 0
        
        # 2. Most seen channels (Top 5)
        query = """
            SELECT v.channel, COUNT(*) as count 
            FROM seen_videos sv
            JOIN videos v ON sv.video_id = v.video_id
            GROUP BY v.channel
            ORDER BY count DESC
            LIMIT 5
        """
        stats['top_channels'] = [{"channel": r['channel'], "count": r['count']} for r in self.fetchall(query)]
        
        # 3. Seen videos with durations
        query = """
            SELECT v.duration 
            FROM seen_videos sv
            JOIN videos v ON sv.video_id = v.video_id
            WHERE v.duration IS NOT NULL AND v.duration != '??:??'
        """
        stats['seen_durations'] = [r['duration'] for r in self.fetchall(query)]
        
        # 4. Watch Later backlog stats
        query = """
            SELECT v.duration 
            FROM playlist_items pi
            JOIN playlists p ON pi.playlist_id = p.id
            JOIN videos v ON pi.video_id = v.video_id
            WHERE p.name = 'Watch Later'
        """
        stats['backlog_durations'] = [r['duration'] for r in self.fetchall(query)]
        
        return stats

    def get_year_stats(self, year):
        """Fetches statistics filtered by a specific year (YYYY)."""
        stats = {}
        year_wildcard = f"{year}%"
        
        # 1. Total seen videos in year
        row = self.fetchone("SELECT COUNT(*) FROM seen_videos WHERE seen_date LIKE ?", (year_wildcard,))
        stats['total_seen'] = row[0] if row else 0
        
        # 2. Most seen channels in year (Top 5)
        query = """
            SELECT v.channel, COUNT(*) as count 
            FROM seen_videos sv
            JOIN videos v ON sv.video_id = v.video_id
            WHERE sv.seen_date LIKE ?
            GROUP BY v.channel
            ORDER BY count DESC
            LIMIT 5
        """
        stats['top_channels'] = [{"channel": r['channel'], "count": r['count']} for r in self.fetchall(query, (year_wildcard,))]
        
        # 3. Seen durations in year
        query = """
            SELECT v.duration 
            FROM seen_videos sv
            JOIN videos v ON sv.video_id = v.video_id
            WHERE sv.seen_date LIKE ? AND v.duration IS NOT NULL AND v.duration != '??:??'
        """
        stats['seen_durations'] = [r['duration'] for r in self.fetchall(query, (year_wildcard,))]
        
        return stats

    def clear_playlist(self, playlist_name, only_seen=False):
        """Removes items from a playlist. If only_seen is True, removes only videos present in seen_videos."""
        if only_seen:
            query = """
                DELETE FROM playlist_items 
                WHERE playlist_id = (SELECT id FROM playlists WHERE name = ?)
                AND video_id IN (SELECT video_id FROM seen_videos)
            """
            c = self.execute(query, (playlist_name,))
            return c.rowcount if c else 0
        else:
            query = """
                DELETE FROM playlist_items 
                WHERE playlist_id = (SELECT id FROM playlists WHERE name = ?)
            """
            c = self.execute(query, (playlist_name,))
            return c.rowcount if c else 0
