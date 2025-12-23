# YTRSS 2.0 📺

A modern, fast, and beautiful TUI (Terminal User Interface) for browsing and organizing YouTube subscriptions via RSS.  
**No algorithms. No distractions. Just your feeds.**

Designed to work seamlessly with [QuickTube](https://github.com/coffe/QuickTube) for distraction-free viewing.

## ✨ New in v2.0 (UX Overhaul)

*   **📊 Live Dashboard:** See new videos, Watch Later count, and Shorts status at a glance.
*   **📂 Organized Layout:** Clear separation between your content (Channels/Videos) and tools.
*   **⚡ Shorts Control:** Toggle YouTube Shorts on/off instantly with `[ S ]`.
*   **📝 Smart Grid:** Video lists are perfectly aligned with icons for status (New `*`, Seen `✔`, Shorts `S`).
*   **🔍 Fuzzy Search:** Type anywhere to instantly filter channels or videos.

## 🚀 Features

*   **Privacy Focused:** Uses RSS feeds. No Google Account login required.
*   **Watch Later:** Built-in local playlist management.
*   **Async Performance:** Fetches 50+ feeds concurrently in seconds.
*   **Metadata Caching:** Saves video durations locally for instant loading.
*   **Keyboard Driven:** Optimized for speed and efficiency.

## 🎮 Controls

### Main Dashboard
| Key | Action |
| :--- | :--- |
| **`R`** | Refresh feeds |
| **`S`** | Toggle Shorts visibility |
| **`+`** | Add Channel (URL) |
| **`-`** | Delete Channel |
| **`M`** | Mark all visible videos as seen |
| **`L`** | Open "Watch Later" |
| **`Q`** | Quit |

### Video List
*   **Navigate:** `↑` / `↓`
*   **Select:** `Enter` (Opens Action Menu)
    *   *Play / DL via QuickTube*
    *   *Add to Watch Later*
    *   *Open in Browser*
*   **Search:** Just type! (e.g., "python tutorial")

## 🛠️ Installation & Setup

### Requirements
*   Python 3.8+
*   `yt-dlp` (For fetching metadata/channel IDs)
*   `wl-copy` (Wayland) or `xclip` (X11) - For clipboard support.

### Running from Source
1.  Clone the repo:
    ```bash
    git clone https://github.com/coffe/ytrss2.git
    cd ytrss2
    ```

2.  Set up Virtual Environment:
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```

3.  Run:
    ```bash
    python ytrss.py
    ```

## ⚙️ Configuration
Data is stored in `~/.config/ytrss/`:
*   `ytRss.opml`: Subscription list (Standard OPML format).
*   `ytrss.db`: Local database (History, Playlists, Metadata).

## 📄 License
MIT

---

**⚠️ Disclaimer:** This project is created for educational purposes only. It is not intended to be used for downloading copyrighted material without permission or for violating YouTube's Terms of Service. Please use this tool responsibly.