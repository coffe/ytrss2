import subprocess
import shutil
import platform
import os
from rich.console import Console

console = Console()

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
    player = get_best_player(preferred_player)
    
    if not player:
        msg = "Error: No suitable video player found. Please install 'mpv' (recommended) or 'vlc'."
        if preferred_player and preferred_player != "auto":
            msg = f"Error: Preferred player '{preferred_player}' not found, and no backup players detected."
        console.print(msg, style="red")
        return False

    mode_text = "Audio Only" if audio_only else "Video"
    console.print(f"Starting {player} ({mode_text})...", style="blue")

    cmd = [player]
    
    # Check if player name contains "mpv" (handles 'mpv' or '/usr/bin/mpv')
    if "mpv" in os.path.basename(player):
        cmd.append("--no-terminal") # Keep the TUI clean
        cmd.append("--force-window") # Ensure window opens even if just audio
        if audio_only:
            cmd.append("--no-video")
    
    # Check if player name contains "vlc"
    elif "vlc" in os.path.basename(player):
        if audio_only:
            cmd.append("--no-video")

    cmd.append(url)

    try:
        # We block here so the TUI waits for the video to finish/close. 
        # This prevents the TUI from refreshing over the player output or stealing focus back immediately.
        subprocess.run(cmd)
        return True
    except Exception as e:
        console.print(f"Error launching player: {e}", style="red")
        return False

def play_local_file(file_path, preferred_player=None):
    """Opens a local video file with the best available player or system default."""
    if not os.path.exists(file_path):
        console.print(f"File not found: {file_path}", style="red")
        return False
        
    # If a specific player is enforced in config, try to use it FIRST
    if preferred_player and preferred_player.lower() != "auto":
        if shutil.which(preferred_player):
            subprocess.run([preferred_player, file_path])
            return True

    system = platform.system()
    
    # 1. Windows / macOS native open
    if system == "Windows":
        os.startfile(file_path)
        return True
    elif system == "Darwin":
        subprocess.run(["open", file_path])
        return True
    
    # 2. Linux / Cross-platform manual player check
    player = get_best_player(preferred_player)
    if player:
        subprocess.run([player, file_path])
        return True
    
    # 3. Fallback to xdg-open on Linux
    if shutil.which("xdg-open"):
        subprocess.run(["xdg-open", file_path])
        return True
            
    console.print("No suitable video player found.", style="yellow")
    return False