#!/usr/bin/env python3
import feedparser
import subprocess
import sys
import os
import shutil
import sqlite3
import asyncio
import aiohttp
import webbrowser
import unicodedata
import json
import platform
import re
import xml.etree.ElementTree as ET
from datetime import datetime

# Reduce Esc key delay (prevents lag when pressing Esc)
os.environ.setdefault('ESCDELAY', '25')

# UI Libraries
try:
    from InquirerPy import inquirer
    from InquirerPy.base.control import Choice
    from InquirerPy.separator import Separator
    from rich.console import Console
    from rich.style import Style
    from rich.panel import Panel
except ImportError:
    print("Error: Missing dependencies.")
    print("Please install requirements: pip install -r requirements.txt")
    sys.exit(1)

console = Console()

# Keybindings mapping 'escape' to 'interrupt'
# 'q' is removed to allow searching for words with 'q'
kb_select = {
    "interrupt": [{"key": "escape"}]
}

kb_input_esc = {
    "interrupt": [{"key": "escape"}]
}

async def ui_select(message, choices, **kwargs):
    kwargs.setdefault("instruction", "[Esc] Back")
    try:
        # Use select for cursor memory and Separator support
        return await inquirer.select(
            message=message, 
            choices=choices, 
            keybindings=kb_select,
            qmark="",
            amark="",
            **kwargs
        ).execute_async()
    except KeyboardInterrupt:
        return None

async def ui_filter(message, choices, **kwargs):
    """Fuzzy search select for filtering lists."""
    kwargs.setdefault("instruction", "[Type to Search] [Esc] Back")
    
    # inquirer.fuzzy does not support Separator, so we must filter them out
    clean_choices = [c for c in choices if not isinstance(c, Separator)]
    
    try:
        return await inquirer.fuzzy(
            message=message,
            choices=clean_choices,
            keybindings=kb_select,
            qmark="",
            amark="",
            **kwargs
        ).execute_async()
    except KeyboardInterrupt:
        return None

async def ui_text(message, **kwargs):
    try:
        return await inquirer.text(message=message, keybindings=kb_input_esc, **kwargs).execute_async()
    except KeyboardInterrupt:
        return None

# Configuration
QUICKTUBE_CMD = "quicktube"
CONFIG_DIR = os.path.expanduser("~/.config/ytrss")
OPML_FILE = os.path.join(CONFIG_DIR, "ytRss.opml")
DB_FILE = os.path.join(CONFIG_DIR, "ytrss.db")
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36"

# Create config directory if it doesn't exist
os.makedirs(CONFIG_DIR, exist_ok=True)

# Global state
duration_cache = {}
SHOW_SHORTS = True  # Default: Show shorts

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

db = DatabaseManager(DB_FILE)

def clipboard_copy(text):
    """Cross-platform clipboard copy."""
    system = platform.system()
    try:
        if system == "Windows":
            # PowerShell Set-Clipboard
            # Escape single quotes for PowerShell
            safe_text = text.replace("'", "''")
            cmd = ["powershell", "-NoProfile", "-Command", f"Set-Clipboard -Value '{safe_text}'"]
            subprocess.run(cmd, check=False)
        elif system == "Darwin":
             p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
             p.communicate(input=text.encode('utf-8'))
        else:
             # Linux
             if shutil.which("wl-copy"):
                 p = subprocess.Popen(["wl-copy"], stdin=subprocess.PIPE)
                 p.communicate(input=text.encode('utf-8'))
             elif shutil.which("xclip"):
                 p = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
                 p.communicate(input=text.encode('utf-8'))
    except Exception as e:
        console.print(f"Clipboard error: {e}", style="red")

def clear_screen():
    os.system('cls' if platform.system() == 'Windows' else 'clear')

def clean_title(text):
    """Removes emojis and other characters that cause terminal rendering glitches."""
    if not text: return ""
    text = unicodedata.normalize('NFKC', text)
    cleaned = []
    for char in text:
        if ord(char) > 0xFFFF: continue
        category = unicodedata.category(char)
        if category.startswith(('C', 'S')):
            if char in "$-+/%": cleaned.append(char)
            else: cleaned.append(" ")
        else:
            cleaned.append(char)
    text = "".join(cleaned)
    return " ".join(text.split())

def mark_as_seen(video_id, title):
    db.execute("INSERT OR IGNORE INTO seen_videos (video_id, title, seen_date) VALUES (?, ?, ?)",
               (video_id, title, datetime.now().isoformat()))

def mark_all_as_seen(videos):
    now = datetime.now().isoformat()
    data = [(v['id'], v['title'], now) for v in videos]
    db.executemany("INSERT OR IGNORE INTO seen_videos (video_id, title, seen_date) VALUES (?, ?, ?)", data)
    console.print(f"Marked {len(videos)} videos as seen.", style="green")

def get_seen_videos():
    seen = set()
    rows = db.fetchall("SELECT video_id FROM seen_videos")
    for row in rows: seen.add(row[0])
    return seen

def get_cached_metadata():
    metadata = {}
    rows = db.fetchall("SELECT video_id, duration FROM video_metadata")
    for row in rows: metadata[row[0]] = row[1]
    return metadata

def save_metadata(video_id, duration):
    db.execute("INSERT OR REPLACE INTO video_metadata (video_id, duration) VALUES (?, ?)", (video_id, duration))

def add_to_playlist(playlist_name, video):
    row = db.fetchone("SELECT id FROM playlists WHERE name = ?", (playlist_name,))
    if not row: return False
    playlist_id = row[0]
    
    pub_date = ""
    if video.get('published'):
        if isinstance(video['published'], (list, tuple)):
            pub_date = datetime(*video['published'][:6]).isoformat()
        else:
            pub_date = str(video['published'])

    db.execute('''INSERT OR REPLACE INTO videos (video_id, title, channel, url, duration, is_shorts, published_date)
                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
              (video['id'], video['title'], video.get('channel'), video['link'], 
               video.get('duration'), video.get('is_shorts', False), pub_date))
    
    db.execute("INSERT OR IGNORE INTO playlist_items (playlist_id, video_id) VALUES (?, ?)",
              (playlist_id, video['id']))
    return True

def get_playlist_videos(playlist_name):
    videos = []
    rows = db.fetchall('''SELECT v.* FROM videos v
                     JOIN playlist_items pi ON v.video_id = pi.video_id
                     JOIN playlists p ON pi.playlist_id = p.id
                     WHERE p.name = ?
                     ORDER BY pi.added_at DESC''', (playlist_name,))
    for row in rows:
        videos.append({
            'id': row['video_id'],
            'title': row['title'],
            'link': row['url'],
            'channel': row['channel'],
            'duration': row['duration'],
            'is_shorts': bool(row['is_shorts']),
            'published': row['published_date'],
            'is_seen': False
        })
    return videos

def remove_from_playlist(playlist_name, video_id):
    db.execute('''DELETE FROM playlist_items 
                 WHERE video_id = ? AND playlist_id = (SELECT id FROM playlists WHERE name = ?)''',
              (video_id, playlist_name))
    return True

async def get_video_duration(video_url, video_id):
    if video_id in duration_cache and duration_cache[video_id] != "??:??":
        return duration_cache[video_id]
    
    # Try light-weight HTML scrap first
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(video_url, headers={"User-Agent": USER_AGENT}, timeout=5) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    # Look for <meta itemprop="duration" content="PT3M45S">
                    match = re.search(r'itemprop="duration" content="PT(\d+H)?(\d+M)?(\d+S)?"', html)
                    if match:
                        h = match.group(1)[:-1] if match.group(1) else "0"
                        m = match.group(2)[:-1] if match.group(2) else "0"
                        s = match.group(3)[:-1] if match.group(3) else "0"
                        
                        if int(h) > 0:
                            duration = f"{h}:{m.zfill(2)}:{s.zfill(2)}"
                        else:
                            duration = f"{m}:{s.zfill(2)}"
                        
                        duration_cache[video_id] = duration
                        save_metadata(video_id, duration)
                        return duration
    except: pass

    # Fallback to yt-dlp
    try:
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp", "--get-duration", video_url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL
        )
        stdout, _ = await proc.communicate()
        if stdout:
            duration = stdout.decode().strip()
            if ':' in duration or duration.isdigit():
                if duration.isdigit(): duration = f"0:{duration.zfill(2)}"
                duration_cache[video_id] = duration
                save_metadata(video_id, duration)
                return duration
    except: pass
    return "??:??"

def load_feeds_from_opml():
    if not os.path.exists(OPML_FILE): return []
    urls = []
    try:
        tree = ET.parse(OPML_FILE)
        root = tree.getroot()
        for outline in root.findall(".//outline"):
            url = outline.get('xmlUrl')
            if url: urls.append(url)
    except: pass
    return urls

async def resolve_rss_url_async(url):
    if "xml" in url or "feed" in url: return url
    console.print(f"Resolving channel ID for: {url} ...", style="dim")
    try:
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp", "--dump-json", "--flat-playlist", "--playlist-items", "1", url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await proc.communicate()
        if proc.returncode == 0 and stdout:
            data = json.loads(stdout.decode().splitlines()[0])
            channel_id = data.get("playlist_channel_id") or data.get("channel_id") or data.get("playlist_id")
            if channel_id and channel_id.startswith("UC"):
                return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    except: pass
    return url

async def add_feed_to_opml_async(url):
    url = await resolve_rss_url_async(url)
    console.print(f"Verifying link: {url} ...", style="dim")
    try:
        loop = asyncio.get_running_loop()
        d = await loop.run_in_executor(None, lambda: feedparser.parse(url, agent=USER_AGENT))
        
        if not d.feed.get('title') and not d.entries:
             console.print("Error: Not a valid RSS feed.", style="red")
             return
        channel_title = d.feed.get('title', 'Unknown Channel')
    except: return

    try:
        if os.path.exists(OPML_FILE):
            tree = ET.parse(OPML_FILE)
            root = tree.getroot()
            body = root.find('body')
        else:
            root = ET.Element('opml', version="1.0")
            ET.SubElement(root, 'head')
            body = ET.SubElement(root, 'body')
            tree = ET.ElementTree(root)
            
        for outline in body.findall('outline'):
            if outline.get('xmlUrl') == url:
                console.print(f"Channel already exists: {outline.get('title')}", style="yellow")
                return

        ET.SubElement(body, 'outline', {'text': channel_title, 'title': channel_title, 'type': 'rss', 'xmlUrl': url})
        tree.write(OPML_FILE, encoding='UTF-8', xml_declaration=True)
        console.print(f"Added: {channel_title}", style="green")
    except Exception as e:
        console.print(f"Could not save: {e}", style="red")

async def remove_channel_ui():
    if not os.path.exists(OPML_FILE): return
    tree = ET.parse(OPML_FILE)
    root = tree.getroot()
    body = root.find('body')
    outlines = body.findall('outline')
    
    choices = []
    for i, node in enumerate(outlines):
        title = node.get('title') or node.get('text') or "Unknown"
        choices.append(Choice(value=i, name=title))
    
    if not choices: return
    choices.append(Choice(value=-1, name="Cancel"))
    
    idx = await ui_filter(message="Select channel to remove:", choices=choices)
    
    if idx is None or idx == -1:
        return
    
    if idx != -1:
        body.remove(outlines[idx])
        tree.write(OPML_FILE, encoding='UTF-8', xml_declaration=True)
        console.print("Channel removed.", style="green")

def get_resource_path(relative_path):
    try: base_path = sys._MEIPASS
    except: base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def show_help():
    help_text = """
    YTRSS 2.0 - Keyboard Controls (InquirerPy)

    Navigation:
    - Up/Down Arrows: Move cursor
    - Type to search/filter (Automatic)
    - Enter: Select item

    Actions:
    - Select a video to open the Action Menu:
      * Play (starts QuickTube)
      * Watch Later (saves to local playlist)
      * Open in Browser
      * Remove (if in playlist)

    Main Menu:
    - [r] Refresh feeds
    - [a] Add channel
    - [m] Mark all seen
    - [s] Toggle Shorts
    """
    console.print(Panel(help_text, title="Help"))
    input("Press Enter to continue...")

async def fetch_feed(session, url):
    try:
        async with session.get(url, headers={"User-Agent": USER_AGENT}) as response:
            if response.status == 200: return await response.text()
    except: return None

async def fetch_and_parse_feed(session, url):
    xml_data = await fetch_feed(session, url)
    if not xml_data: return None
    loop = asyncio.get_running_loop()
    # Run feedparser in a thread pool to avoid blocking the event loop
    return await loop.run_in_executor(None, feedparser.parse, xml_data)

async def show_video_menu(videos, playlist_name=None):
    global SHOW_SHORTS

    if not SHOW_SHORTS:
        videos = [v for v in videos if not v.get('is_shorts')]
        if not videos:
            console.print("No videos to show (Shorts are hidden).", style="yellow")
            await asyncio.sleep(1.5)
            return

    # Metadata fetching logic (unchanged)
    to_fetch = [v for v in videos[:40] if v['duration'] == "??:??"]
    if to_fetch:
        console.print(f"Fetching metadata for {len(to_fetch)} videos...", style="dim")
        sem = asyncio.Semaphore(5)
        async def fetch_and_update(v):
            async with sem:
                dur = await get_video_duration(v['link'], v['id'])
                v['duration'] = dur
                if dur != "??:??":
                    try:
                        parts = dur.split(':')
                        if len(parts) == 2:
                            m, s = int(parts[0]), int(parts[1])
                            if m == 0 or (m == 1 and s == 0): v['is_shorts'] = True
                    except: pass
        await asyncio.gather(*(fetch_and_update(v) for v in to_fetch))
        
        if not SHOW_SHORTS:
            videos = [v for v in videos if not v.get('is_shorts')]
            if not videos: return

    while True:
        clear_screen()
        choices = []
        for i, v in enumerate(videos):
            # Format Date
            if isinstance(v['published'], str):
                try: dt = datetime.fromisoformat(v['published']).strftime("%m-%d")
                except: dt = "??"
            else:
                try: dt = datetime(*v['published'][:6]).strftime("%m-%d")
                except: dt = "??"

            # Icons and Styling (Single-width characters for perfect alignment)
            seen_mark = "*" if not v['is_seen'] else " " # Star for new, space for seen
            shorts_mark = "S" if v.get('is_shorts') else " "
            duration = v.get('duration', '??:??')
            safe_title = clean_title(v['title'])
            
            # Channel truncation (16 chars for better fit)
            channel_name = v['channel'][:16]
            
            # Grid Layout: [Status] Date | Dur | Shorts | Channel | Title
            label = f"{seen_mark} {dt} │ {duration:>7} │ {shorts_mark} │ {channel_name:<16} │ {safe_title}"
            
            choices.append(Choice(value=i, name=label))
        
        if not choices:
            console.print("List is empty.", style="yellow")
            break

        choices.append(Choice(value=-1, name="[Go Back]"))

        title_suffix = "(Shorts hidden)" if not SHOW_SHORTS else ""
        idx = await ui_filter(
            message=f"Select video {title_suffix}:", 
            choices=choices,
            max_height="70%"
        )

        if idx is None or idx == -1: break
        
        video = videos[idx]
        
        # Action Menu for selected video
        action_choices = [
            Choice("play", name="Play (QuickTube)"),
            Choice("watch_later", name="Add to Watch Later"),
            Choice("browser", name="Open in Browser"),
            Choice("cancel", name="Cancel")
        ]
        
        if playlist_name:
            action_choices.insert(3, Choice("remove", name="Remove from Playlist"))

        action = await ui_select(
            message=f"Action for: {clean_title(video['title'])}", 
            choices=action_choices
        )
        
        if action is None or action == "cancel":
            continue
            
        elif action == "play":
            mark_as_seen(video['id'], video['title'])
            video['is_seen'] = True
            console.print(f"Starting QuickTube for: {video['title']}", style="green")
            try:
                clipboard_copy(video['link'])
                subprocess.run([QUICKTUBE_CMD])
            except Exception as e:
                console.print(f"Error launching: {e}", style="red")
        
        elif action == "watch_later":
            if add_to_playlist("Watch Later", video):
                console.print(f"Added to Watch Later.", style="green")
            else:
                console.print("Failed to add.", style="red")
            await asyncio.sleep(1.0)

        elif action == "browser":
            webbrowser.open(video['link'])
            mark_as_seen(video['id'], video['title'])
            video['is_seen'] = True
        
        elif action == "remove":
            if remove_from_playlist(playlist_name, video['id']):
                console.print("Removed.", style="green")
                del videos[idx]
            else:
                console.print("Could not remove.", style="red")
            await asyncio.sleep(1.0)

async def main_async():
    global duration_cache, SHOW_SHORTS
    db.connect()
    duration_cache = get_cached_metadata()
    
    while True:
        feeds = load_feeds_from_opml()
        seen_ids = get_seen_videos()
        
        if not feeds:
            console.print("\nNo channels found.", style="yellow")
        
        all_videos_by_channel = {}
        all_videos_flat = []

        with console.status("[bold green]Fetching feeds...") as status:
            async with aiohttp.ClientSession() as session:
                tasks = [fetch_and_parse_feed(session, url) for url in feeds]
                results = await asyncio.gather(*tasks)

        for d in results:
            if not d: continue
            try:
                ch_name = clean_title(d.feed.get('title', 'Unknown'))
                ch_videos = []
                for entry in d.entries:
                    vid_id = entry.get('id', entry.link)
                    if vid_id.startswith('yt:video:'): vid_id = vid_id.replace('yt:video:', '')
                    
                    title = entry.title
                    
                    # Try to find duration in media_group if available
                    duration = duration_cache.get(vid_id, "??:??")
                    if duration == "??:??":
                        # Some RSS parsers/feeds include duration in media_content
                        media_group = entry.get('media_group', {})
                        if 'duration' in media_group:
                            duration = media_group['duration']
                        elif 'media_content' in entry and len(entry['media_content']) > 0:
                            if 'duration' in entry['media_content'][0]:
                                duration = entry['media_content'][0]['duration']

                    is_shorts = "#shorts" in title.lower() or "#shorts" in entry.get('summary', '').lower()
                    v = {
                        'id': vid_id, 'title': title, 'link': entry.link,
                        'published': entry.get('published_parsed'),
                        'channel': ch_name, 'is_seen': vid_id in seen_ids,
                        'is_shorts': is_shorts,
                        'duration': duration
                    }
                    if v['duration'] != "??:??":
                         try:
                            parts = v['duration'].split(':')
                            if len(parts) == 2 and (int(parts[0]) == 0 or (int(parts[0]) == 1 and int(parts[1]) == 0)):
                                v['is_shorts'] = True
                         except: pass
                    if v['published']:
                        ch_videos.append(v)
                        all_videos_flat.append(v)
                all_videos_by_channel[ch_name] = ch_videos
            except: pass
        
        all_videos_flat.sort(key=lambda x: x['published'], reverse=True)

        should_refresh = False
        last_selection = None

        while not should_refresh:
            clear_screen()
            
            # Dashboard Statistics
            unread_total = len([v for v in all_videos_flat if not v['is_seen']])
            wl_videos = get_playlist_videos("Watch Later")
            wl_count = len(wl_videos)
            shorts_status = "ON" if SHOW_SHORTS else "OFF"
            
            # Create Dashboard Panel
            stats_text = (
                f"[bold white]New Videos:[/bold white] [green]{unread_total}[/green]  │  "
                f"[bold white]Watch Later:[/bold white] [cyan]{wl_count}[/cyan]  │  "
                f"[bold white]Shorts:[/bold white] [yellow]{shorts_status}[/yellow]"
            )
            console.print(Panel(stats_text, title="[bold cyan]YTRSS 2.0 DASHBOARD[/bold cyan]", border_style="blue", expand=False))
            
            choices = []
            
            # Blank line
            choices.append(Separator(""))

            # 1. BROWSE (Priority Content)
            choices.append(Separator("  ─ [ BROWSE ] ────────────────────────────"))
            choices.append(Separator(""))
            choices.append(Choice(value="ALL", name=f"   ✨  All Videos ({unread_total} new)"))
            choices.append(Choice(value="WL", name=f"   📂  Watch Later ({wl_count})"))
            
            # 2. CHANNELS (Content)
            if all_videos_by_channel:
                choices.append(Separator(""))
                choices.append(Separator("  ─ [ CHANNELS ] ──────────────────────────"))
                choices.append(Separator(""))
                for name in sorted(all_videos_by_channel.keys()):
                    count = len([v for v in all_videos_by_channel[name] if not v['is_seen']])
                    # Visual cue: '>' or '📺' makes it look like a folder/object
                    choices.append(Choice(value=f"CH:{name}", name=f"   📺  {name} ({count})"))
            
            # 3. SYSTEM / TOOLS (Bottom Controls)
            choices.append(Separator(""))
            choices.append(Separator("  ─ [ SYSTEM ] ────────────────────────────"))
            choices.append(Separator(""))
            
            # Tool styling: Looks like buttons [ Key ]
            shorts_status = "ON" if SHOW_SHORTS else "OFF"
            choices.append(Choice("refresh", "   [ R ] Refresh feeds"))
            choices.append(Choice("shorts",  f"   [ S ] Toggle Shorts ({shorts_status})"))
            choices.append(Choice("add",     "   [ + ] Add channel"))
            choices.append(Choice("del",     "   [ - ] Delete channel"))
            choices.append(Choice("mark",    "   [ M ] Mark all as seen"))
            choices.append(Choice("help",    "   [ ? ] Help"))
            choices.append(Choice("quit",    "   [ Q ] Quit"))

            # Use fuzzy filter for main menu to allow quick navigation
            selection = await ui_filter(
                message="YTRSS Main Menu [ Esc = Back/quit ]", 
                choices=choices,
                max_height="90%"
            )

            if selection is None or selection == "quit": 
                clear_screen()
                sys.exit()
            
            # Remember selection for next loop
            last_selection = selection

            if selection == "help": show_help()
            elif selection == "shorts": 
                SHOW_SHORTS = not SHOW_SHORTS
                continue
            elif selection == "refresh": 
                should_refresh = True
            elif selection == "add":
                url = await ui_text(message="Paste RSS URL:")
                if url: 
                    await add_feed_to_opml_async(url)
                    await asyncio.sleep(1.5)
                should_refresh = True
            elif selection == "del":
                await remove_channel_ui()
                should_refresh = True
            elif selection == "mark":
                unseen = [v for v in all_videos_flat if not v['is_seen']]
                mark_all_as_seen(unseen)
                await asyncio.sleep(1.5)
                for v in unseen: v['is_seen'] = True
            elif selection == "ALL":
                await show_video_menu(all_videos_flat[:60]) # Limit to 60 for perf
            elif selection == "WL":
                wl_videos = get_playlist_videos("Watch Later")
                current_seen = get_seen_videos()
                for v in wl_videos: v['is_seen'] = v['id'] in current_seen
                await show_video_menu(wl_videos, playlist_name="Watch Later")
            elif selection.startswith("CH:"):
                name = selection.split("CH:")[1]
                videos = sorted(all_videos_by_channel[name], key=lambda x: x['published'], reverse=True)
                await show_video_menu(videos)

if __name__ == "__main__":
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        clear_screen()
        pass