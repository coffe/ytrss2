import platform
import subprocess
import shutil
import os
import unicodedata
import sys
from rich.console import Console

console = Console()

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

def get_resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)
