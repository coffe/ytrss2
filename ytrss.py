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
from src.config import ConfigManager
from src.database import DatabaseManager
from src.utils import clipboard_copy, clear_screen, clean_title, get_resource_path
from src.ui import ui_select, ui_filter, ui_text, Choice, Separator, Console, Panel, Style, inquirer
from datetime import datetime

# Reduce Esc key delay (prevents lag when pressing Esc)
os.environ.setdefault('ESCDELAY', '25')

console = Console()

# Configuration
QUICKTUBE_CMD = "quicktube"
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

db = DatabaseManager(DB_FILE)

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

def get_all_playlists():
    rows = db.fetchall("SELECT name, is_system_list FROM playlists ORDER BY is_system_list DESC, name ASC")
    return [{"name": r['name'], "is_system": bool(r['is_system_list'])} for r in rows]

def create_playlist(name):
    try:
        db.execute("INSERT INTO playlists (name, is_system_list) VALUES (?, 0)", (name,))
        return True
    except:
        return False

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
        ]
        
        if cfg.get_bool('General', 'multi_playlists'):
            action_choices.append(Choice("add_to", name="Add to Playlist..."))

        action_choices.extend([
            Choice("browser", name="Open in Browser"),
            Choice("cancel", name="Cancel")
        ])
        
        if playlist_name:
            action_choices.insert(len(action_choices)-2, Choice("remove", name="Remove from Playlist"))

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

async def show_settings_menu():
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
            is_newyear = use_themes and ((month == 12 and day >= 30) or (month == 1 and day <= 2))

            if is_christmas:
                title = "[bold red]❄️  YTRSS CHRISTMAS EDITION  ❄️[/bold red]"
                border = "green"
                stats_text = (
                    f"[bold white]New Videos:[/bold white] [bold red]{unread_total}[/bold red]  │  "
                    f"[bold white]Watch Later:[/bold white] [bold green]{wl_count}[/bold green]  │  "
                    f"[bold white]Shorts:[/bold white] [bold yellow]{shorts_status}[/bold yellow]"
                )
            elif is_newyear:
                title = "[bold bright_white]✧･ﾟ:* [/bold bright_white][bold gold1]HAPPY NEW YEAR[/bold gold1][bold bright_white] *:･ﾟ✧[/bold bright_white]"
                border = "yellow"
                stats_text = (
                    f"[grey50]｡ﾟ•[/grey50] [bold white]Videos:[/bold white] [bold gold1]{unread_total}[/bold gold1] [grey50]•[/grey50]  "
                    f"[grey50]•[/grey50] [bold white]Saved:[/bold white] [bold gold1]{wl_count}[/bold gold1] [grey50]•[/grey50]  "
                    f"[grey50]•[/grey50] [bold white]Shorts:[/bold white] [bold gold1]{shorts_status}[/bold gold1] [grey50]•ﾟ｡[/grey50]"
                )
            else:
                title = "[bold white]YTRSS 2.0[/bold white]"
                border = "blue"
                stats_text = (
                    f"New Videos: [bold blue]{unread_total}[/bold blue]  │  "
                    f"Watch Later: [bold blue]{wl_count}[/bold blue]  │  "
                    f"Shorts: [bold blue]{shorts_status}[/bold blue]"
                )

            console.print(Panel(stats_text, title=title, border_style=border, expand=False, padding=(0, 1) if not is_newyear else (1, 2)))
            
            choices = []
            choices.append(Separator(""))

            # 1. BROWSE
            if is_christmas:
                browse_title = "  ─ [ BROWSE ] ❄️ * ❄️ ──────────────────────"
            elif is_newyear:
                browse_title = "  ─ [ BROWSE ] ✧･ﾟ:* ───────────────────────"
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
                    ch_title = "  ─ [ CHANNELS ] ✧･ﾟ:* ─────────────────────"
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
                sys_title = "  ─ [ SYSTEM ] ✧･ﾟ:* ───────────────────────"
            else:
                sys_title = "  ─ [ SYSTEM ] ────────────────────────────"
            
            choices.append(Separator(sys_title))
            choices.append(Separator(""))
            
            choices.append(Choice("refresh", "   [ R ] Refresh feeds"))
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
                max_height="90%"
            )

            if selection is None or selection == "quit": 
                clear_screen()
                sys.exit()
            
            if selection == "help": show_help()
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