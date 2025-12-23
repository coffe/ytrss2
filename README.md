# ytrss 📺

A fast and lightweight TUI tool for browsing and watching YouTube subscriptions via RSS, directly in your terminal. Built for Linux with the Unix philosophy in mind.

Designed to work seamlessly with [QuickTube](https://github.com/coffe/QuickTube) (or other video players).

## ✨ Features

*   **Blazing Fast:** Fetches all RSS feeds asynchronously (concurrently) at startup.
*   **Watch Later Playlist:** Save videos to a local "Watch Later" list directly from the interface.
*   **Clean TUI:** Navigate easily with arrow keys and search/filter by pressing `/`.
*   **Shorts Handling:** Automatically identifies Shorts (< 60s) and lets you toggle their visibility instantly.
*   **Smart:** Tracks watched videos and caches video durations in a local SQLite database.
*   **OPML Support:** Easily import/export your subscriptions.
*   **Portable:** Builds into a single standalone binary with no dependencies.

## 🚀 Installation

### Option 1: Build from Source (Recommended)
You only need Python 3 installed.

```bash
git clone https://github.com/coffe/ytrss.git
cd ytrss
./build.sh
```

This creates an executable in `dist/ytrss`. Copy it to your `$PATH`:

```bash
cp dist/ytrss ~/bin/  # or /usr/local/bin/
```

## 🎮 Usage

Start the program:

```bash
ytrss
```

### ⌨️ Shortcuts & Controls

#### Main Menu
*   **Up/Down Arrows**: Navigate the menu.
*   **Enter**: Select channel or playlist.
*   **`/`**: Search/Filter menu items.
*   **`r`**: Refresh feeds.
*   **`a`**: Add new channel (paste RSS URL).
*   **`d`**: Delete a channel.
*   **`m`**: Mark all *new* videos as seen.
*   **`s`**: Show/Hide Shorts (toggle).
*   **`?`**: Show help within the app.
*   **`q`**: Quit.

#### Video List
*   **Up/Down Arrows**: Navigate the list.
*   **Enter**: Play video (copies link + starts QuickTube).
*   **`l`**: Add to "Watch Later".
*   **`b`**: Open video in Web Browser.
*   **`d`**: Remove video (only works in playlists like Watch Later).
*   **`/`**: Search/Filter videos (e.g., type "linux").
*   **`q`**: Go back to main menu.

## ⚙️ Configuration
All data is stored in `~/.config/ytrss/`:
*   `ytRss.opml`: Your subscriptions.
*   `ytrss.db`: Database with history, metadata, and playlists.

## 🔧 Requirements
*   Python 3.8+
*   `yt-dlp` (for fetching video durations/metadata).
*   `wl-copy` (Wayland) or `xclip` (X11) for clipboard handling.
*   [`quicktube`](https://github.com/coffe/QuickTube) (recommended for playback, but can be adapted).

## 📄 License
MIT

---

**⚠️ Disclaimer:** This project is created for educational purposes only. It is not intended to be used for downloading copyrighted material without permission or for violating YouTube's Terms of Service. Please use this tool responsibly.
