import platform
import subprocess
import shutil
import os
import unicodedata
import sys
import urllib.request
import stat
from rich.console import Console

import pyperclip

console = Console()

def clipboard_copy(text):
    """Cross-platform clipboard copy using pyperclip."""
    try:
        pyperclip.copy(text)
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

def get_resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

def duration_to_seconds(duration_str):
    """Converts HH:MM:SS or MM:SS to total seconds."""
    if not duration_str or duration_str == "??:??": return 0
    try:
        parts = duration_str.split(':')
        if len(parts) == 3: # HH:MM:SS
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
        elif len(parts) == 2: # MM:SS
            return int(parts[0]) * 60 + int(parts[1])
        elif len(parts) == 1: # SS
            return int(parts[0])
    except: return 0
    return 0

def seconds_to_readable(seconds):
    """Converts seconds to a readable string like '2h 15m' or '45m 10s'."""
    if seconds <= 0: return "0m"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    
    parts = []
    if h > 0: parts.append(f"{h}h")
    if m > 0: parts.append(f"{m}m")
    if h == 0 and s > 0: parts.append(f"{s}s")
    
    return " ".join(parts) if parts else "0m"

import asyncio

async def download_video(url, output_dir, video_id):
    """Downloads a video using yt-dlp and returns the absolute file path."""
    os.makedirs(output_dir, exist_ok=True)
    
    # Template: Title [id].ext
    output_template = os.path.join(output_dir, "%(title)s [%(id)s].%(ext)s")
    
    # Get filename first (simulation)
    try:
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp", "--get-filename", "-o", output_template, url,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            console.print(f"Error getting filename: {stderr.decode()}", style="red")
            return None
        
        filename = stdout.decode().strip()
        
        # Download
        console.print(f"Downloading to: {filename}", style="blue")
        proc_dl = await asyncio.create_subprocess_exec(
            "yt-dlp", "-o", output_template, url,
            stdout=asyncio.subprocess.PIPE,  # Capture output to avoid cluttering UI too much
            stderr=asyncio.subprocess.PIPE
        )
        
        # We could parse stdout to show progress bar here in the future
        _, stderr_dl = await proc_dl.communicate()
        
        if proc_dl.returncode == 0:
            return os.path.abspath(filename)
        else:
            console.print(f"Download failed: {stderr_dl.decode()}", style="red")
            return None

    except Exception as e:
        console.print(f"Exception during download: {e}", style="red")
        return None

def check_dependencies():
    """Checks for necessary tools and returns a list of missing ones."""
    missing = []
    
    if not shutil.which("yt-dlp"):
        missing.append("yt-dlp")
    
    if not shutil.which("mpv") and not shutil.which("vlc"):
         missing.append("mpv/vlc")
         
    if not shutil.which("ffmpeg"):
        missing.append("ffmpeg")
        
    return missing

def get_js_engine():
    """Find a supported JavaScript engine (Node, QuickJS, Deno)."""
    for engine in ["node", "quickjs", "deno"]:
        if shutil.which(engine):
            return engine
    return None

def get_ytdlp_base_cmd(cookie_browser=None):
    """Constructs the base command for yt-dlp with essential stability flags."""
    cmd = ["yt-dlp", "--no-warnings", "--force-ipv4"]
    
    # Network Stability
    # (force-ipv4 is already added above)

    # JS Engine (Fixes throttling/signatures)
    js_engine = get_js_engine()
    if js_engine:
        cmd.extend(["--js-runtime", js_engine])

    # Auth
    if cookie_browser and cookie_browser.lower() != "none":
        cmd.extend(["--cookies-from-browser", cookie_browser])
    
    return cmd

def install_ytdlp():
    """Downloads and installs the latest yt-dlp binary."""
    system = platform.system()
    filename = "yt-dlp.exe" if system == "Windows" else "yt-dlp"
    
    # Target directory: ~/.local/bin is standard on Linux/Mac
    home = os.path.expanduser("~")
    local_bin = os.path.join(home, ".local", "bin")
    
    if system == "Windows":
        # On Windows, maybe use the current directory or a 'bin' folder
        local_bin = os.path.join(os.getcwd(), "bin")
    
    os.makedirs(local_bin, exist_ok=True)
    target_path = os.path.join(local_bin, filename)
    
    url = f"https://github.com/yt-dlp/yt-dlp/releases/latest/download/{filename}"
    if system == "Darwin": 
        url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos"

    console.print(f"Downloading yt-dlp to {target_path}...", style="blue")
    
    try:
        urllib.request.urlretrieve(url, target_path)
        
        # Make executable on Unix
        if system != "Windows":
            st = os.stat(target_path)
            os.chmod(target_path, st.st_mode | stat.S_IEXEC)
            
        # Add to PATH for this session if not already there
        if local_bin not in os.environ["PATH"]:
             os.environ["PATH"] = local_bin + os.pathsep + os.environ["PATH"]
             
        console.print("Successfully installed yt-dlp.", style="green")
        return True
    except Exception as e:
        console.print(f"Failed to install yt-dlp: {e}", style="red")
        return False

