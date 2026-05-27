import subprocess
import shutil
import platform
import os
from rich.console import Console
from src.logger import get_logger
from src.config import ConfigManager
from src.utils import get_js_engine, get_clean_env

console = Console()
logger = get_logger()

# Load config to check for browser cookies
CONF_FILE = os.path.expanduser("~/.config/ytrss/ytrss.conf")
cfg = ConfigManager(CONF_FILE)

def get_best_player(preferred_player=None):
    """Finds the best available player (mpv preferred, or user specified)."""
    # 1. Check preferred player if specified
    if preferred_player and preferred_player.lower() != "auto":
        if shutil.which(preferred_player):
            return preferred_player
            
    # 2. Auto detection
    if shutil.which("mpv"): return "mpv"
    if shutil.which("vlc"): return "vlc"
    return None

def play_stream(url, audio_only=False, preferred_player=None):
    """Streams a URL using the preferred player or falls back to mpv/vlc."""
    # Reload config to get latest browser setting
    cfg.config.read(CONF_FILE)
    cookie_browser = cfg.get_str('General', 'cookie_browser')
    
    player = get_best_player(preferred_player)

    if not player:
        msg = "Error: No suitable video player found. Please install 'mpv' (recommended) or 'vlc'."
        if preferred_player and preferred_player != "auto":
            msg = f"Error: Preferred player '{preferred_player}' not found, and no backup players detected."
        console.print(msg, style="red")
        logger.error(msg)
        return False

    mode_text = "Audio Only" if audio_only else "Video"
    console.print(f"Starting {player} ({mode_text})...", style="blue")

    cmd = [player]

    # Check if player name contains "mpv" (handles 'mpv' or '/usr/bin/mpv')
    if "mpv" in os.path.basename(player):
        cmd.append("--force-window")
        
        # Explicit path to yt-dlp (important if it's in ~/.local/bin)
        ytdlp_path = shutil.which("yt-dlp")
        if ytdlp_path:
            cmd.append(f"--script-opts=ytdl_hook-ytdl_path={ytdlp_path}")
        else:
            logger.warning("yt-dlp not found in PATH! mpv might fail to play YouTube links.")

        # Format selection
        if audio_only:
            cmd.append("--no-video")
            cmd.append("--ytdl-format=bestaudio/best")
            
        # Handle Cookies / Client spoofing
        raw_options = []
        
        # ALWAYS force IPv4 to avoid 403/TLS errors on unstable IPv6 connections
        # Note: force-ipv4 takes no value, so we pass empty string after =
        raw_options.append("force-ipv4=")
        
        # Fix for "No supported JavaScript runtime could be found"
        js_engine = get_js_engine()
        if js_engine:
            raw_options.append(f"js-runtime={js_engine}")
        
        if cookie_browser and cookie_browser.lower() != "none":
            # Use browser cookies (Strongest auth)
            console.print(f"Using cookies from: {cookie_browser}", style="dim")
            logger.info(f"Using cookies from {cookie_browser}")
            raw_options.append(f"cookies-from-browser={cookie_browser}")
        else:
            # Fallback: Use iOS client spoofing to avoid 403 Forbidden on generic requests
            raw_options.append("extractor-args=youtube:player_client=ios")
            
        if raw_options:
            cmd.append(f"--ytdl-raw-options={','.join(raw_options)}")

    # Check if player name contains "vlc"
    elif "vlc" in os.path.basename(player):
        if audio_only:
            cmd.append("--no-video")

    cmd.append(url)
    
    # Log the full command for debugging
    cmd_str = " ".join(f"'{c}'" if " " in c else c for c in cmd)
    logger.info(f"Launching player command: {cmd_str}")

    try:
        # IMPORTANT: We do NOT use capture_output=True here because:
        # 1. We want the user to see mpv's output/errors directly in the terminal if it fails.
        # 2. mpv might need to interact with the terminal.
        # 3. Blocking here ensures the TUI waits for the video to finish.
        result = subprocess.run(cmd, env=get_clean_env())
        
        if result.returncode != 0:
            logger.error(f"Player exited with error code {result.returncode}")
            console.print(f"Player exited with error code {result.returncode}. Try changing cookie settings if 403 occurs.", style="yellow")
            
        return True
    except Exception as e:
        console.print(f"Error launching player: {e}", style="red")
        logger.error(f"Exception launching player: {e}")
        return False

def play_local_file(file_path, preferred_player=None):
    """Opens a local video file with the best available player or system default."""
    if not os.path.exists(file_path):
        console.print(f"File not found: {file_path}", style="red")
        logger.error(f"File not found: {file_path}")
        return False
        
    # If a specific player is enforced in config, try to use it FIRST
    if preferred_player and preferred_player.lower() != "auto":
        if shutil.which(preferred_player):
            try:
                subprocess.run([preferred_player, file_path], env=get_clean_env())
                return True
            except Exception as e:
                logger.error(f"Failed to run preferred player {preferred_player}: {e}")

    system = platform.system()
    
    try:
        # 1. Windows / macOS native open
        if system == "Windows":
            os.startfile(file_path)
            return True
        elif system == "Darwin":
            subprocess.run(["open", file_path], env=get_clean_env())
            return True
        
        # 2. Linux / Cross-platform manual player check
        player = get_best_player(preferred_player)
        if player:
            cmd = [player, file_path]
            logger.info(f"Playing local file: {' '.join(cmd)}")
            subprocess.run(cmd, env=get_clean_env())
            return True
        
        # 3. Fallback to xdg-open on Linux
        if shutil.which("xdg-open"):
            subprocess.run(["xdg-open", file_path], env=get_clean_env())
            return True
            
        console.print("No suitable video player found.", style="yellow")
        logger.warning("No suitable player found for local file.")
        return False
    except Exception as e:
        logger.error(f"Error playing local file: {e}")
        return False