import asyncio
import json
import os
import shutil
from rich.console import Console
from src.ui import ui_select, Choice
from src.utils import clean_title
from src.logger import get_logger
from src.config import ConfigManager

console = Console()
logger = get_logger()

# Load config
CONF_FILE = os.path.expanduser("~/.config/ytrss/ytrss.conf")
cfg = ConfigManager(CONF_FILE)

# Helper to format file size
def format_size(size_bytes):
    if not size_bytes: return "N/A"
    return f"{size_bytes / (1024*1024):.1f}MB"

async def get_video_formats(url):
    """Fetches available formats using yt-dlp -J."""
    cfg.config.read(CONF_FILE)
    cookie_browser = cfg.get_str('General', 'cookie_browser')
    
    console.print("Fetching video information...", style="dim")
    try:
        from src.utils import get_ytdlp_base_cmd
        cmd = get_ytdlp_base_cmd(cookie_browser)
        cmd.append("-J")
        cmd.append(url)
        
        logger.debug(f"Fetching formats: {' '.join(cmd)}")
        
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode != 0:
            console.print(f"Error fetching info: {stderr.decode()}", style="red")
            logger.error(f"yt-dlp JSON error: {stderr.decode()}")
            return None, None

        data = json.loads(stdout.decode())
        formats = data.get("formats", [])
        
        # Group by resolution/height
        unique_resolutions = {} # height -> format info

        for f in formats:
            # Skip video-only or audio-only streams usually (we want best combos), 
            # BUT yt-dlp -f bestvideo+bestaudio merges them. 
            # We just want to identify valid resolutions here.
            
            # Logic adapted from QuickTube to find unique heights
            vcodec = f.get("vcodec", "none")
            if vcodec == "none": continue # Skip audio-only streams for the video list
            
            height = f.get("height")
            if not height: continue

            # Determine quality metrics to pick the "best" representation for this height
            # (e.g. prioritize higher bitrate/fps for the label)
            fps = f.get("fps") or 0
            filesize = f.get("filesize") or f.get("filesize_approx") or 0
            tbr = f.get("tbr") or 0
            
            if height not in unique_resolutions:
                unique_resolutions[height] = f
            else:
                existing = unique_resolutions[height]
                e_fps = existing.get("fps") or 0
                e_size = existing.get("filesize") or existing.get("filesize_approx") or 0
                e_tbr = existing.get("tbr") or 0
                
                # Logic: Higher FPS > Higher Bitrate/Size
                replace = False
                if fps > e_fps: replace = True
                elif fps == e_fps:
                    if tbr > e_tbr: replace = True
                
                if replace:
                    unique_resolutions[height] = f

        # Create sorted list (highest res first)
        results = []
        for h in sorted(unique_resolutions.keys(), reverse=True):
            f = unique_resolutions[h]
            results.append({
                'height': h,
                'fps': f.get("fps") or 0,
                'ext': f.get("ext"),
                'filesize': f.get("filesize") or f.get("filesize_approx")
            })
            
        return results, data.get("title", "Unknown")

    except Exception as e:
        console.print(f"Error parsing formats: {e}", style="red")
        logger.error(f"Exception parsing formats: {e}")
        return None, None

async def select_and_download(url, download_path, video_id):
    """Interactive download flow similar to QuickTube."""
    
    # Refresh config
    cfg.config.read(CONF_FILE)
    cookie_browser = cfg.get_str('General', 'cookie_browser')
    
    formats, title = await get_video_formats(url)
    if not formats:
        return None

    choices = []
    
    # Check for ffmpeg presence
    has_ffmpeg = shutil.which("ffmpeg") is not None
    if not has_ffmpeg:
        console.print("Warning: ffmpeg not found. Merging video+audio might fail.", style="yellow")
        logger.warning("ffmpeg not found! Download might fail for high quality streams.")

    # 1. Video Options
    choices.append(Choice("separator_video", "--- Video ---"))
    for f in formats:
        # Align columns using f-string padding
        # Height: 5 chars right-aligned (e.g. "1080p")
        # FPS: 8 chars left-aligned (e.g. "60.0fps ")
        # Ext: 4 chars left-aligned (e.g. "mp4 ")
        # Size: 8 chars right-aligned (e.g. " 123.5MB")
        
        res_str = f"{f['height']}p"
        fps_str = f"{f['fps']}fps"
        size_str = format_size(f['filesize'])
        
        label = f"{res_str:>5} │ {fps_str:<8} │ {f['ext']:<4} │ {size_str:>8}"
        
        # We pass a tuple/dict as value to know what to download
        value = {"type": "video", "height": f['height']} 
        choices.append(Choice(value, name=label))
    
    # 2. Audio Option
    choices.append(Choice("separator_audio", "--- Audio ---"))
    choices.append(Choice({"type": "audio"}, name="Audio Only (Opus/Best Audio)"))
    
    choices.append(Choice("cancel", name="[ Cancel ]"))

    selection = await ui_select(
        message=f"Download: {clean_title(title)}",
        choices=choices
    )

    if selection == "cancel" or isinstance(selection, str): # Handle separator selection if bug
        return None

    # Construct yt-dlp command based on selection
    os.makedirs(download_path, exist_ok=True)
    
    # Safe filename template
    output_template = os.path.join(download_path, "%(title)s [%(id)s].%(ext)s")
    
    from src.utils import get_ytdlp_base_cmd
    cmd = get_ytdlp_base_cmd(cookie_browser)
    cmd.extend(["--force-overwrites", "--embed-metadata", "--embed-thumbnail"])
    
    if selection["type"] == "audio":
        console.print("Downloading Audio...", style="blue")
        cmd.extend([
            "-f", "bestaudio/best",
            "-x", "--audio-format", "opus",
            "-o", output_template
        ])
    else:
        # Video
        h = selection["height"]
        console.print(f"Downloading Video ({h}p)...", style="blue")
        # Format selection: Best video with this height + best audio, merge to mp4/mkv
        
        if has_ffmpeg:
            cmd.extend([
                "-f", f"bestvideo[height={h}]+bestaudio/best[height={h}]/best",
                "--merge-output-format", "mp4"
            ])
        else:
            # Fallback if no ffmpeg: just grab best format that contains both or fallback to best
            logger.warning("No ffmpeg: downloading single file 'best' format, ignoring specific resolution request to be safe.")
            cmd.extend(["-f", "best"])
            
        cmd.extend(["-o", output_template])

    cmd.append(url)
    
    # Log command
    logger.info(f"Download command: {' '.join(cmd)}")

    # Execute
    # We allow stdout to pass through so user sees progress bar from yt-dlp
    try:
        # Get filename first for database saving
        logger.debug("Resolving filename...")
        
        # Need to include cookies here too for filename resolution if it requires auth
        fname_cmd = ["yt-dlp", "--get-filename", "-o", output_template]
        if cookie_browser and cookie_browser.lower() != "none":
            fname_cmd.extend(["--cookies-from-browser", cookie_browser])
        fname_cmd.append(url)
        
        filename_proc = await asyncio.create_subprocess_exec(
            *fname_cmd,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        fname_out, fname_err = await filename_proc.communicate()
        
        if filename_proc.returncode != 0:
             logger.error(f"Filename resolution failed: {fname_err.decode()}")
             console.print("Could not resolve filename.", style="red")
             return None

        final_filename = fname_out.decode().strip()
        # If audio, extension might change to .opus, but let's trust get-filename or adjust
        if selection["type"] == "audio":
             # yt-dlp --get-filename might return .webm or .m4a before conversion
             # This is tricky. Let's just return the path it *likely* ends up at.
             final_filename = os.path.splitext(final_filename)[0] + ".opus"

        process = await asyncio.create_subprocess_exec(*cmd)
        await process.wait()
        
        if process.returncode == 0:
            # Verify file exists (sometimes extensions differ)
            if os.path.exists(final_filename):
                return final_filename
            else:
                # Try finding it if extension differs
                base = os.path.splitext(final_filename)[0]
                for ext in [".mp4", ".mkv", ".opus", ".webm", ".m4a"]:
                    if os.path.exists(base + ext):
                        return base + ext
            return final_filename
        else:
            console.print("Download failed.", style="red")
            logger.error("Download process exited with error.")
            return None

    except Exception as e:
        console.print(f"Error: {e}", style="red")
        logger.error(f"Download exception: {e}")
        return None
