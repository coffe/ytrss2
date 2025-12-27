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
import configparser
from typing import List, Dict, Optional, Set, Any, Tuple
from src.config import ConfigManager
from src.database import DatabaseManager
from src.downloader import select_and_download
from src.player import play_stream, play_local_file
from src.utils import clipboard_copy, clear_screen, clean_title, get_resource_path, duration_to_seconds, seconds_to_readable, download_video, check_dependencies, install_ytdlp
from src.ui import ui_select, ui_filter, ui_text, Choice, Separator, Console, Panel, Style, inquirer, show_stats_ui, Group, Align
from datetime import datetime

# Reduce Esc key delay (prevents lag when pressing Esc)
os.environ.setdefault('ESCDELAY', '25')

console = Console()

# Configuration
CONFIG_DIR = os.path.expanduser("~/.config/ytrss")
OPML_FILE = os.path.join(CONFIG_DIR, "ytRss.opml")
DB_FILE = os.path.join(CONFIG_DIR, "ytrss.db")
CONF_FILE = os.path.join(CONFIG_DIR, "ytrss.conf")
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36"

# Create config directory if it doesn't exist
os.makedirs(CONFIG_DIR, exist_ok=True)
cfg = ConfigManager(CONF_FILE)

# Global state
duration_cache = {}
SHOW_SHORTS = cfg.get_bool('General', 'show_shorts')
DOWNLOAD_PATH = cfg.get_str('General', 'download_path')
PLAYER_CMD = cfg.get_str('General', 'player')

db = DatabaseManager(DB_FILE)

def mark_as_seen(video_id: str, title: str) -> None:
    """Marks a single video as seen in the database."""
    db.execute("INSERT OR IGNORE INTO seen_videos (video_id, title, seen_date) VALUES (?, ?, ?)",
               (video_id, title, datetime.now().isoformat()))

def save_download_path(video_id: str, path: Optional[str]) -> None:
    """Updates the local file path for a downloaded video."""
    db.execute("UPDATE videos SET download_path = ? WHERE video_id = ?", (path, video_id))

def mark_all_as_seen(videos: List[Dict[str, Any]]) -> None:
    """Marks a list of video objects as seen in bulk."""
    now = datetime.now().isoformat()
    data = [(v['id'], v['title'], now) for v in videos]
    db.executemany("INSERT OR IGNORE INTO seen_videos (video_id, title, seen_date) VALUES (?, ?, ?)", data)
    console.print(f"Marked {len(videos)} videos as seen.", style="green")

def get_seen_videos() -> Set[str]:
    """Retrieves a set of all seen video IDs."""
    seen = set()
    rows = db.fetchall("SELECT video_id FROM seen_videos")
    for row in rows: seen.add(row[0])
    return seen

def get_cached_metadata() -> Dict[str, str]:
    """Loads cached video durations from the database."""
    metadata = {}
    rows = db.fetchall("SELECT video_id, duration FROM video_metadata")
    for row in rows: metadata[row[0]] = row[1]
    return metadata

def save_metadata(video_id: str, duration: str) -> None:
    """Saves a video's duration to the metadata cache."""
    db.execute("INSERT OR REPLACE INTO video_metadata (video_id, duration) VALUES (?, ?)", (video_id, duration))

def add_to_playlist(playlist_name: str, video: Dict[str, Any]) -> bool:
    """
    Adds a video to a specific playlist.
    
    Args:
        playlist_name (str): Name of the target playlist.
        video (dict): Video object containing metadata (id, title, link, etc).
        
    Returns:
        bool: True if successful, False if playlist doesn't exist.
    """
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

def get_playlist_videos(playlist_name: str) -> List[Dict[str, Any]]:
    """
    Retrieves all videos from a playlist.
    
    Args:
        playlist_name (str): Name of the playlist to query.
        
    Returns:
        list: A list of video dictionaries.
    """
    videos = []
    rows = db.fetchall('''SELECT v.* FROM videos v
                     JOIN playlist_items pi ON v.video_id = pi.video_id
                     JOIN playlists p ON pi.playlist_id = p.id
                     WHERE p.name = ?
                     ORDER BY pi.added_at DESC''', (playlist_name,))
    for row in rows:
        # Check if file actually exists
        dl_path = row['download_path']
        if dl_path and not os.path.exists(dl_path):
            dl_path = None # File moved or deleted
            
        videos.append({
            'id': row['video_id'],
            'title': row['title'],
            'link': row['url'],
            'channel': row['channel'],
            'duration': row['duration'],
            'is_shorts': bool(row['is_shorts']),
            'published': row['published_date'],
            'download_path': dl_path,
            'is_seen': False
        })
    return videos

def get_all_playlists() -> List[Dict[str, Any]]:
    """Returns a list of all playlists (both system and user-created)."""
    rows = db.fetchall("SELECT name, is_system_list FROM playlists ORDER BY is_system_list DESC, name ASC")
    return [{"name": r['name'], "is_system": bool(r['is_system_list'])} for r in rows]

def create_playlist(name: str) -> bool:
    """Creates a new user playlist."""
    try:
        db.execute("INSERT INTO playlists (name, is_system_list) VALUES (?, 0)", (name,))
        return True
    except:
        return False

def remove_from_playlist(playlist_name: str, video_id: str) -> bool:
    """Removes a video from a specific playlist."""
    db.execute('''DELETE FROM playlist_items 
                 WHERE video_id = ? AND playlist_id = (SELECT id FROM playlists WHERE name = ?)''',
              (video_id, playlist_name))
    return True

async def get_video_duration(video_url: str, video_id: str) -> str:
    """
    Fetches video duration using HTML scraping (fast) or yt-dlp (reliable).
    
    Args:
        video_url (str): The URL of the YouTube video.
        video_id (str): The YouTube Video ID.
        
    Returns:
        str: Duration string (e.g. "04:20") or "??:??" if failed.
    """
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

def load_feeds_from_opml() -> List[str]:
    """Parses the OPML file and returns a list of RSS URLs."""
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

async def resolve_rss_url_async(url: str) -> str:
    """
    Attempts to resolve a generic YouTube channel URL into an RSS feed URL.
    Uses yt-dlp to find the underlying channel ID if necessary.
    """
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

async def add_feed_to_opml_async(url: str) -> None:
    """
    Verifies a URL and adds it to the OPML subscription list if valid.
    Checks for duplicates before adding.
    """
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

async def remove_channel_ui() -> None:
    """Displays an interactive UI to remove a channel from the OPML file."""
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

def show_help():
    help_text = """
    [bold]YTRSS 2.0 - Help & Controls[/bold]

    [bold cyan]Navigation[/bold cyan]
    • [bold]Up/Down[/bold]: Move selection
    • [bold]Type[/bold]:   Search/Filter content automatically
    • [bold]Enter[/bold]:  Select item or confirm action

    [bold cyan]Main Menu Shortcuts[/bold cyan]
    • [bold]r[/bold]: Refresh feeds
    • [bold]a[/bold]: Add new channel (RSS URL)
    • [bold]m[/bold]: Mark all displayed videos as seen
    • [bold]s[/bold]: Toggle Shorts visibility
    • [bold],[/bold]: Open Settings
    • [bold]q[/bold]: Quit

    [bold cyan]Video Actions[/bold cyan]
    Select a video to:
    • Play (Stream or Local)
    • Download
    • Add to Watch Later / Playlists
    • Open in Browser

    [bold cyan]Configuration[/bold cyan]
    Edit [bold]~/.config/ytrss/ytrss.conf[/bold] to customize:
    • [bold]player[/bold]: Set video player (e.g., 'mpv', 'vlc', or 'auto')
    • [bold]show_shorts[/bold]: True/False
    • [bold]seasonal_themes[/bold]: True/False
    """
    console.print(Panel(help_text, title="Help", border_style="green"))
    input("Press Enter to continue...")

async def fetch_feed(session: aiohttp.ClientSession, url: str) -> Optional[str]:
    """Fetches raw XML content from a URL asynchronously."""
    try:
        async with session.get(url, headers={"User-Agent": USER_AGENT}) as response:
            if response.status == 200: return await response.text()
    except: return None

async def fetch_and_parse_feed(session: aiohttp.ClientSession, url: str) -> Optional[Any]:
    """
    Fetches and parses an RSS feed.
    Runs feedparser in a separate thread to avoid blocking the asyncio loop.
    """
    xml_data = await fetch_feed(session, url)
    if not xml_data: return None
    loop = asyncio.get_running_loop()
    # Run feedparser in a thread pool to avoid blocking the event loop
    return await loop.run_in_executor(None, feedparser.parse, xml_data)

async def show_video_menu(videos: List[Dict[str, Any]], playlist_name: Optional[str] = None) -> None:
    """
    Displays the interactive video list menu.
    
    Args:
        videos (list): List of video dictionaries to display.
        playlist_name (str, optional): Name of the current playlist (enables specific actions like remove).
    """
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
            dl_mark = "💾" if v.get('download_path') else " "
            duration = v.get('duration', '??:??')
            safe_title = clean_title(v['title'])
            
            # Channel truncation (16 chars for better fit)
            channel_name = v['channel'][:16]
            
            # Grid Layout: [Status] Date | Dur | Shorts | DL | Channel | Title
            label = f"{seen_mark} {dt} │ {duration:>7} │ {shorts_mark} │ {dl_mark} │ {channel_name:<16} │ {safe_title}"
            
            choices.append(Choice(value=i, name=label))
        
        if not choices:
            console.print("List is empty.", style="yellow")
            break

        choices.append(Choice(value=-1, name="[Go Back]"))
        
        if playlist_name and videos:
             choices.append(Choice(value="download_all", name="[Download All Videos in List]"))
             choices.append(Choice(value="clean_seen", name="[🗑️  Remove WATCHED Videos]"))
             choices.append(Choice(value="clear_all", name="[🔥 Clear Playlist]"))

        title_suffix = "(Shorts hidden)" if not SHOW_SHORTS else ""
        idx = await ui_filter(
            message=f"Select video {title_suffix}:", 
            choices=choices,
            max_height="70%"
        )

        if idx == "download_all":
            # Bulk Download Logic
            to_download = [v for v in videos if not v.get('download_path')]
            if not to_download:
                console.print("All videos in this list are already downloaded.", style="green")
                await asyncio.sleep(1.5)
                continue

            confirm = await ui_select(
                message=f"Download {len(to_download)} videos to {DOWNLOAD_PATH}?", 
                choices=[Choice("yes", "Yes, start downloading"), Choice("no", "No, cancel")]
            )
            
            if confirm == "yes":
                for i, vid in enumerate(to_download, 1):
                    console.print(f"Downloading {i}/{len(to_download)}: {vid['title']}...", style="blue")
                    path = await download_video(vid['link'], DOWNLOAD_PATH, vid['id'])
                    if path:
                        save_download_path(vid['id'], path)
                        vid['download_path'] = path
                        console.print("Done.", style="green")
                    else:
                        console.print("Failed.", style="red")
                console.print("Batch download complete.", style="bold green")
                await asyncio.sleep(2.0)
            continue
        
        elif idx == "clean_seen":
            count = db.clear_playlist(playlist_name, only_seen=True)
            if count > 0:
                console.print(f"Removed {count} watched videos.", style="green")
                # Update local list
                videos = [v for v in videos if not v.get('is_seen')]
            else:
                console.print("No watched videos found in this playlist.", style="yellow")
            await asyncio.sleep(1.5)
            continue
            
        elif idx == "clear_all":
            confirm = await ui_select(
                message=f"Are you sure you want to EMPTY '{playlist_name}'?", 
                choices=[Choice("no", "No, keep them"), Choice("yes", "YES, DELETE ALL")]
            )
            if confirm == "yes":
                db.clear_playlist(playlist_name, only_seen=False)
                videos = [] # Empty list
                console.print("Playlist cleared.", style="green")
                await asyncio.sleep(1.0)
            continue

        if idx is None or idx == -1: break
        
        video = videos[idx]
        
        # Action Menu for selected video
        action_choices = []
        
        # Priority: Play Local if available
        if video.get('download_path'):
             action_choices.append(Choice("play_local", name="▶️  Play Local File"))
             action_choices.append(Choice("delete_local", name="🗑️  Delete Local File"))
        
        player_label = "Stream Video"
        if PLAYER_CMD != "auto":
             player_label += f" ({PLAYER_CMD})"
        elif shutil.which("mpv"):
             player_label += " (mpv)"
        elif shutil.which("vlc"):
             player_label += " (vlc)"

        action_choices.append(Choice("play_stream", name=f"▶️  {player_label}"))
        action_choices.append(Choice("play_audio", name="🎧  Stream Audio Only"))
        
        if not video.get('download_path'):
            action_choices.append(Choice("download", name="💾  Download..."))

        action_choices.append(Choice("watch_later", name="CLOCK  Add to Watch Later")) # Using text CLOCK placeholder if emoji fails, but standardizing on emoji in UI usually works. Let's stick to standard chars or consistent emoji.
        # Actually, let's just use the previous style.
        action_choices[-1] = Choice("watch_later", name="⏱️  Add to Watch Later")

        
        if cfg.get_bool('General', 'multi_playlists'):
            action_choices.append(Choice("add_to", name="➕  Add to Playlist..."))

        action_choices.extend([
            Choice("browser", name="🌐  Open in Browser"),
            Choice("cancel", name="❌  Cancel")
        ])
        
        if playlist_name:
            action_choices.insert(len(action_choices)-2, Choice("remove", name="🗑️  Remove from Playlist"))

        action = await ui_select(
            message=f"Action for: {clean_title(video['title'])}", 
            choices=action_choices
        )
        
        if action is None or action == "cancel":
            continue
            
        elif action == "play_local":
            if play_local_file(video['download_path'], preferred_player=PLAYER_CMD):
                mark_as_seen(video['id'], video['title'])
                video['is_seen'] = True
            else:
                await asyncio.sleep(2.0)

        elif action == "download":
            # Using new interactive downloader
            path = await select_and_download(video['link'], DOWNLOAD_PATH, video['id'])
            if path:
                save_download_path(video['id'], path)
                video['download_path'] = path
                console.print(f"Saved to: {path}", style="green")
            else:
                # If path is None, user might have cancelled or error occurred.
                # select_and_download handles error printing.
                pass
            await asyncio.sleep(1.5)

        elif action == "delete_local":
            try:
                os.remove(video['download_path'])
                save_download_path(video['id'], None)
                video['download_path'] = None
                console.print("File deleted.", style="green")
            except Exception as e:
                console.print(f"Error deleting file: {e}", style="red")
            await asyncio.sleep(1.0)

        elif action == "play_stream":
            mark_as_seen(video['id'], video['title'])
            video['is_seen'] = True
            play_stream(video['link'], audio_only=False, preferred_player=PLAYER_CMD)
        
        elif action == "play_audio":
            mark_as_seen(video['id'], video['title'])
            video['is_seen'] = True
            play_stream(video['link'], audio_only=True, preferred_player=PLAYER_CMD)
        
        elif action == "watch_later":
            if add_to_playlist("Watch Later", video):
                console.print(f"Added to Watch Later.", style="green")
            else:
                console.print("Failed to add.", style="red")
            await asyncio.sleep(1.0)

        elif action == "add_to":
            playlists = get_all_playlists()
            p_choices = [Choice(p['name'], name=f"   {p['name']}") for p in playlists]
            p_choices.append(Separator(""))
            p_choices.append(Choice("__new__", name="   [+] Create New Playlist"))
            p_choices.append(Choice("__cancel__", name="   [x] Cancel"))
            
            p_selection = await ui_select(message="Select Playlist:", choices=p_choices)
            
            if p_selection == "__new__":
                new_name = await ui_text(message="Enter Playlist Name:")
                if new_name:
                    if create_playlist(new_name):
                        if add_to_playlist(new_name, video):
                            console.print(f"Created and added to: {new_name}", style="green")
                        else:
                            console.print(f"Created {new_name} but failed to add video.", style="yellow")
                    else:
                        console.print(f"Could not create playlist '{new_name}'.", style="red")
                await asyncio.sleep(1.5)
            elif p_selection and p_selection != "__cancel__":
                if add_to_playlist(p_selection, video):
                    console.print(f"Added to: {p_selection}", style="green")
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

async def show_settings_menu() -> None:
    """Displays the settings menu to toggle app preferences."""
    global SHOW_SHORTS
    while True:
        clear_screen()
        choices = [
            Choice("toggle_shorts", f"Show Shorts: {'[ON]' if cfg.get_bool('General', 'show_shorts') else '[OFF]'}"),
            Choice("toggle_themes", f"Seasonal Themes: {'[ON]' if cfg.get_bool('General', 'seasonal_themes') else '[OFF]'}"),
            Choice("toggle_multi",  f"Enable Multi-Playlists (WIP): {'[ON]' if cfg.get_bool('General', 'multi_playlists') else '[OFF]'}"),
            Separator(""),
            Choice("back", "[ Go Back ]")
        ]
        
        selection = await ui_select(message="Settings Menu:", choices=choices)
        
        if selection == "back" or selection is None:
            break
        elif selection == "toggle_shorts":
            new_val = not cfg.get_bool('General', 'show_shorts')
            cfg.set_val('General', 'show_shorts', new_val)
            SHOW_SHORTS = new_val
        elif selection == "toggle_themes":
            new_val = not cfg.get_bool('General', 'seasonal_themes')
            cfg.set_val('General', 'seasonal_themes', new_val)
        elif selection == "toggle_multi":
            new_val = not cfg.get_bool('General', 'multi_playlists')
            cfg.set_val('General', 'multi_playlists', new_val)

async def main_async() -> None:
    """
    Main application loop.
    Handles startup checks, feed fetching, dashboard rendering, and user input.
    """
    global duration_cache, SHOW_SHORTS
    db.connect()
    duration_cache = get_cached_metadata()
    
    # Check dependencies at startup
    missing = check_dependencies()
    if missing:
        clear_screen()
        console.print(Panel(f"[bold yellow]Warning: Missing tools: {', '.join(missing)}[/bold yellow]", title="System Check"))
        
        if "yt-dlp" in missing:
            choice = await ui_select(
                message="yt-dlp is required for downloading and streaming. Install it now?",
                choices=[Choice("yes", "Yes, install it"), Choice("no", "No, I'll fix it later")]
            )
            if choice == "yes":
                install_ytdlp()
                await asyncio.sleep(2)
        
        if "mpv/vlc" in missing or "ffmpeg" in missing:
            console.print("\n[bold cyan]Note:[/bold cyan] For best experience, please install [bold]mpv[/bold] and [bold]ffmpeg[/bold] using your package manager.")
            console.print("Example: [green]sudo apt install mpv ffmpeg[/green]\n")
            await asyncio.sleep(3)

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
            
            # Playlists data
            all_playlists = get_all_playlists()
            playlists_counts = {}
            for p in all_playlists:
                p_videos = get_playlist_videos(p['name'])
                playlists_counts[p['name']] = len(p_videos)

            wl_count = playlists_counts.get("Watch Later", 0)
            shorts_status = "ON" if SHOW_SHORTS else "OFF"
            
            # Create Dashboard Panel (Conditional Theme)
            use_themes = cfg.get_bool('General', 'seasonal_themes')
            month = datetime.now().month
            day = datetime.now().day
            
            is_christmas = use_themes and month == 12 and (20 <= day <= 26)
            is_newyear = use_themes and ((month == 12 and day >= 27) or (month == 1 and day <= 2))

            subtitle = None
            if is_christmas:
                header = "[bold red]*  YTRSS CHRISTMAS EDITION  *[/bold red]"
                border = "green"
                subtitle = "[bold white]*  *[/bold white]"
                stats_text = (
                    f"[bold white]New Videos:[/bold white] [bold red]{unread_total}[/bold red]  │  "
                    f"[bold white]Watch Later:[/bold white] [bold green]{wl_count}[/bold green]  │  "
                    f"[bold white]Shorts:[/bold white] [bold yellow]{shorts_status}[/bold yellow]"
                )
                panel_content = Group(
                    Align.center(header),
                    Align.center(stats_text)
                )
            elif is_newyear:
                # Countdown Logic
                target = datetime(2026, 1, 1, 0, 0, 0)
                now_dt = datetime.now()
                if now_dt.year >= 2026:
                     countdown_str = "Happy New Year!"
                else:
                    diff = target - now_dt
                    days = diff.days
                    hours, remainder = divmod(diff.seconds, 3600)
                    minutes, _ = divmod(remainder, 60)
                    countdown_str = f"{days}d {hours}h {minutes}m"

                # Simplified header without ambiguous width characters
                header = "[bold bright_white]✨ [/bold bright_white][bold gold1]HAPPY NEW YEAR[/bold gold1][bold bright_white] ✨[/bold bright_white]"
                border = "yellow"
                val_style = "[bold red]"
                
                # Clean stats line without problematic decorators
                stats_line = (
                    f"[grey50]•[/grey50] [bold white]Videos:[/bold white] {val_style}{unread_total}[/] [grey50]•[/grey50]  "
                    f"[grey50]•[/grey50] [bold white]Saved:[/bold white] {val_style}{wl_count}[/] [grey50]•[/grey50]  "
                    f"[grey50]•[/grey50] [bold white]Shorts:[/bold white] {val_style}{shorts_status}[/] [grey50]•[/grey50]"
                )
                countdown_line = f"[bold gold1]⏳ 2026 in: {countdown_str}[/bold gold1]"
                
                # Use Group and Align to center everything robustly
                
                panel_content = Group(
                
                    Align.center(header),
                
                    Align.center(stats_line),
                
                    Align.center(countdown_line)
                
                )
                
                subtitle = "[bold grey50]Stardust Edition[/bold grey50]"
                
            else:
                header = "[bold white]YTRSS 2.0[/bold white]"
                border = "blue"
                stats_text = (
                    f"New Videos: [bold blue]{unread_total}[/bold blue]  │  "
                    f"Watch Later: [bold blue]{wl_count}[/bold blue]  │  "
                    f"Shorts: [bold blue]{shorts_status}[/bold blue]"
                )
                panel_content = Group(
                    Align.center(header),
                    Align.center(stats_text)
                )

            console.print(Panel(
                panel_content, 
                subtitle=subtitle, 
                border_style=border, 
                expand=False, 
                padding=(0, 1) if not is_newyear else (0, 2)
            ))

            choices = []
            choices.append(Separator(""))

            # 1. BROWSE
            if is_christmas:
                browse_title = "  ─ [ BROWSE ] ❄️ * ❄️ ──────────────────────"
            elif is_newyear:
                browse_title = "  ─ [ BROWSE ] ────────────────────────────"
            else:
                browse_title = "  ─ [ BROWSE ] ────────────────────────────"
            
            choices.append(Separator(browse_title))
            choices.append(Separator(""))
            
            all_icon = "   ✨  " if is_newyear else ("   🎄  " if is_christmas else "   ⭐  ")
            wl_icon = "   🥂  " if is_newyear else ("   🎁  " if is_christmas else "   📂  ")
            
            choices.append(Choice(value="ALL", name=f"{all_icon}All Videos ({unread_total} new)"))
            
            multi_on = cfg.get_bool('General', 'multi_playlists')
            for p in all_playlists:
                if not multi_on and p['name'] != "Watch Later":
                    continue
                
                count = playlists_counts.get(p['name'], 0);
                icon = wl_icon if p['name'] == "Watch Later" else "   📜  "
                choices.append(Choice(value=f"PL:{p['name']}", name=f"{icon}{p['name']} ({count})"))
            
            # 2. CHANNELS
            if all_videos_by_channel:
                choices.append(Separator(""))
                if is_christmas:
                    ch_title = "  ─ [ CHANNELS ] ❄️ * ❄️ ────────────────────"
                elif is_newyear:
                    ch_title = "  ─ [ CHANNELS ] ──────────────────────────"
                else:
                    ch_title = "  ─ [ CHANNELS ] ──────────────────────────"
                choices.append(Separator(ch_title))
                choices.append(Separator(""))
                
                if is_christmas: ch_icon = "   🎅  "
                elif is_newyear: ch_icon = "   🔔  "
                else:            ch_icon = "   📺  "
                
                for name in sorted(all_videos_by_channel.keys()):
                    count = len([v for v in all_videos_by_channel[name] if not v['is_seen']])
                    choices.append(Choice(value=f"CH:{name}", name=f"{ch_icon}{name} ({count})"))
            
            # 3. SYSTEM
            choices.append(Separator(""))
            if is_christmas:
                sys_title = "  ─ [ SYSTEM ] ❄️ * ❄️ ──────────────────────"
            elif is_newyear:
                sys_title = "  ─ [ SYSTEM ] ────────────────────────────"
            else:
                sys_title = "  ─ [ SYSTEM ] ────────────────────────────"
            
            choices.append(Separator(sys_title))
            choices.append(Separator(""))
            
            choices.append(Choice("refresh", "   [ R ] Refresh feeds"))
            choices.append(Choice("stats",   "   [ I ] Insights / Statistics"))
            choices.append(Choice("update_tools", "   [ U ] Update yt-dlp"))
            choices.append(Choice("settings", "   [ , ] Settings"))
            
            if multi_on:
                choices.append(Choice("del_playlist", "   [ - ] Delete playlist"))

            choices.append(Choice("add",     "   [ + ] Add channel"))
            choices.append(Choice("del",     "   [ - ] Delete channel"))
            choices.append(Choice("mark",    "   [ M ] Mark all as seen"))
            choices.append(Choice("help",    "   [ ? ] Help"))
            choices.append(Choice("quit",    "   [ Q ] Quit"))

            selection = await ui_filter(
                message="YTRSS Main Menu", 
                choices=choices,
                max_height="70%"
            )
            if selection is None or selection == "quit": 
                clear_screen()
                sys.exit()
            
            if selection == "help": show_help()
            elif selection == "stats":
                current_year = None
                while True:
                    if current_year:
                        stats_data = db.get_year_stats(current_year)
                    else:
                        stats_data = db.get_stats_data()
                    
                    result = await show_stats_ui(stats_data, duration_to_seconds, seconds_to_readable, year=current_year)
                    
                    if result == "back":
                        break
                    elif result == "year_2025":
                        current_year = "2025"
            elif selection == "update_tools":
                install_ytdlp()
                await asyncio.sleep(2.0)
            elif selection == "settings": 
                await show_settings_menu()
                continue
            elif selection == "refresh": 
                should_refresh = True
            elif selection == "del_playlist":
                playlists = [p for p in get_all_playlists() if not p['is_system']]
                if not playlists:
                    console.print("No custom playlists to delete.", style="yellow")
                    await asyncio.sleep(1.0)
                    continue
                p_choices = [Choice(p['name'], name=f"   {p['name']}") for p in playlists]
                p_choices.append(Choice("__cancel__", name="   [x] Cancel"))
                p_to_del = await ui_select(message="Select Playlist to DELETE:", choices=p_choices)
                if p_to_del and p_to_del != "__cancel__":
                    db.execute("DELETE FROM playlists WHERE name = ?", (p_to_del,))
                    console.print(f"Playlist '{p_to_del}' deleted.", style="green")
                    await asyncio.sleep(1.0)
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
            elif selection == "WL" or selection == "PL:Watch Later":
                wl_videos = get_playlist_videos("Watch Later")
                current_seen = get_seen_videos()
                for v in wl_videos: v['is_seen'] = v['id'] in current_seen
                await show_video_menu(wl_videos, playlist_name="Watch Later")
            elif selection.startswith("PL:"):
                p_name = selection.split("PL:")[1]
                p_videos = get_playlist_videos(p_name)
                current_seen = get_seen_videos()
                for v in p_videos: v['is_seen'] = v['id'] in current_seen
                await show_video_menu(p_videos, playlist_name=p_name)
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