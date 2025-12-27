# Project: YT-RSS Discovery (Feeder to QuickTube)

## 1. Overview
A lightweight CLI program acting as a "Discovery" module for YouTube content. The program fetches metadata via RSS, presents a list of new videos, and delegates playback/downloading to QuickTube.

Philosophy: Unix philosophy – Do one thing well and connect with other tools.

## 2. Current Status (Implemented 2025-12-20)
The program is now fully functional with the following features:

*   **Asynchronous Fetching:** Uses `asyncio` and `aiohttp` to fetch all RSS feeds in parallel.
*   **Subscription Management:** Reads and writes channels to `ytRss.opml`. Support for adding and removing channels directly in the UI.
*   **Database:** SQLite (`ytrss.db`) is used to:
    *   Mark videos as **[WATCHED]**.
    *   Cache video durations (`duration`) for faster loading.
*   **Metadata & Duration:** Fetches video duration in the background via `yt-dlp` (asynchronously with semaphore limit).
*   **TUI (Text User Interface):** Built with `simple-term-menu`.
    *   Navigation with arrow keys.
    *   Search/Filtering by typing directly in the menu.
    *   Shows channel name, time, duration, and Shorts marker.
*   **Shorts Detection:** Automatically marks videos < 61 seconds or with `#shorts` tags.
*   **QuickTube Integration:** Copies selected video URL to system clipboard (`wl-copy`) and launches `quicktube`.

## 3. Technical Stack
*   **Language:** Python 3.13+
*   **RSS Parsing:** `feedparser`
*   **Network:** `aiohttp` (Async HTTP)
*   **UI:** `simple-term-menu`
*   **Database:** `sqlite3` (Built-in)
*   **External Dependencies:** `yt-dlp` (for metadata), `quicktube` (for playback), `wl-copy` (for clipboard).

## 4. Workflow
1.  **Start:** Loads `ytRss.opml` and starts asynchronous feed fetching.
2.  **Menu:** Shows a main menu with all channels + "All videos (Mix)".
3.  **List:** Shows videos sorted by date.
    *   Fetches video duration in background if missing.
4.  **Selection:** User selects video -> URL copied to clipboard -> `quicktube` started.
5.  **History:** Video is marked as watched in the database.

## 5. To-Do / Future Improvements
- [x] Database: Save ID of already viewed videos.
- [x] OPML import/export: Full support via `ytRss.opml`.
- [x] UI: TUI with arrow keys (`simple-term-menu`).
- [x] Shorts detection: Marked in the list.
- [ ] **Shorts filter:** Ability to *hide* Shorts completely from the list (toggle).
- [ ] **Configuration file:** Move hardcoded paths (DB, OPML) to a config.ini or similar.
