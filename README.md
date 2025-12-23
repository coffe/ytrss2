# QuickTube RSS (YTRSS 2.0) 📺

**A modern, lightning-fast TUI for YouTube subscriptions via RSS.**

QuickTube RSS allows you to follow your favorite channels without an account, algorithms, or distractions. It is the perfect companion to the QuickTube video player.

## ✨ Features

*   **📊 Live Dashboard:** Overview of new videos and playlist status.
*   **⚡ Async Fetching:** Concurrent RSS processing for maximum speed.
*   **🧘 Content Control:** Toggle Shorts visibility with one key.
*   **🔍 Fuzzy Search:** Instant filtering of channels and video titles.
*   **📂 Local First:** History and "Watch Later" stored in a local SQLite database.
*   **📦 Standalone:** Can be built into a single binary for easy distribution.

## 🚀 Getting Started

### Prerequisites
*   **Python 3.8+**
*   **yt-dlp:** Required for resolving channel IDs and video durations.
*   **Clipboard:** `wl-copy` (Wayland) or `xclip` (X11) for copying video links.
*   **Player:** [QuickTube](https://github.com/coffe/QuickTube) (recommended) or any player that can handle YouTube URLs.

### Installation (Building from Source)
```bash
git clone https://github.com/coffe/quicktube2.git
cd quicktube2
./build.sh
```
The resulting binary will be located at `bin/ytrss`. You can move it to your path:
```bash
sudo cp bin/ytrss /usr/local/bin/ytrss
```

## 🎮 Keyboard Controls

### Main Menu
| Key | Action |
| :--- | :--- |
| **`R`** | Refresh all feeds |
| **`S`** | Toggle Shorts (ON/OFF) |
| **`+` / `-`** | Add or Remove a channel |
| **`M`** | Mark all visible videos as seen |
| **`L`** | Open Watch Later playlist |
| **`Q`** | Quit and clear terminal |

### Video List
| Key | Action |
| :--- | :--- |
| **`Enter`** | Open Action Menu (Play, Save, Browse) |
| **`Esc`** | Return to Main Menu |
| **`Type`** | Instant fuzzy search/filter |

## ⚙️ Configuration
Files are stored in `~/.config/ytrss/`:
*   `ytRss.opml`: Your subscription list.
*   `ytrss.db`: SQLite database for history and metadata.

## 📄 License
MIT

---

**⚠️ Disclaimer:** This project is for educational purposes only. Use it responsibly and respect YouTube's Terms of Service.