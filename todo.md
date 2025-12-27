# ytrss TODO 📋

## ✅ Completed (2025-12-22)
*   **Watch Later:** Added "Watch Later" playlist function (`l` to add, `d` to remove).
*   **Playlists:** Database structure implemented for local playlists.
*   **UI Improvements:** Added Search (`/`), Help (`?`), and shortcuts (`s` for Shorts toggle).
*   **Browser Fallback:** Added `b` shortcut to open videos directly in the browser.
*   **In-app Help:** Created a help viewer (`?`) and an external `KEYS.md` guide.
*   **UX Refinement:** Removed redundant sub-menus and added direct playback on Enter.
*   **Binary Bundling:** Fixed PyInstaller config to include `KEYS.md` inside the executable.

## 🚀 Next Steps
*   **Smart Link Handling:** 
    *   **Validation:** Verify that a link is a valid RSS feed before adding it to the database/OPML.
    *   **Auto-discovery:** If a link isn't an RSS feed (e.g., a standard YouTube channel URL), try to automatically find the underlying RSS feed URL and add that instead.
*   **Global Search:** Implement a "Search YouTube" feature using `yt-dlp`.
    *   Add `[g] Global Search` to the main menu.
    *   Fetch results using `yt-dlp "ytsearch20:query" --dump-json --flat-playlist`.
*   **Mac Compatibility:** Ensure the tool works on macOS (check `wl-copy` vs `pbcopy`, file paths, notifications etc).

## 💡 Ideas & Improvements
*   **Quick Subscribe:** Option to subscribe to a channel directly from global search results.
*   **Multiple OPML:** Support for multiple categories or folders in the OPML file.
*   **Terminal Players:** Better integration/selection of different terminal-based players.