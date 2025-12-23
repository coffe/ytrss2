# YTRSS 2.0 📺

**The minimalist, distraction-free YouTube RSS client for your terminal.**

YTRSS 2.0 allows you to browse, organize, and watch your YouTube subscriptions without ever opening the YouTube homepage. No algorithms, no ads, no distractions—just the content you subscribed to.

> Hosted in the `quicktube2` repository.

## ✨ Key Features

*   **📊 Dashboard:** Instant overview of new videos, "Watch Later" queue, and Shorts status.
*   **⚡ Blazing Fast:** Asynchronous fetching of 50+ feeds in seconds.
*   **🧘 Distraction Free:** Filter out Shorts with a single keystroke `[ S ]`.
*   **📂 Organized:** Clean TUI with visual separation between content and tools.
*   **💾 Local & Private:** No Google Account needed. Data stored locally.
*   **🛠️ standalone:** Builds into a single binary with zero runtime dependencies.

## 📥 Installation

### Option 1: Build from Source (Recommended)
Since this repository is optimized for building, this is the best way to run it.

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/coffe/quicktube2.git
    cd quicktube2
    ```

2.  **Build the binary:**
    ```bash
    ./build.sh
    ```

3.  **Install:**
    The executable will be in `dist/ytrss`. Move it to your path:
    ```bash
    sudo cp dist/ytrss /usr/local/bin/ytrss
    ```

### Option 2: Run via Python
If you prefer running the script directly:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python ytrss.py
```

## 🎮 Controls

| Key | Context | Action |
| :--- | :--- | :--- |
| **`↑` / `↓`** | Navigation | Move selection |
| **`Enter`** | Videos | Open Action Menu (Play, Watch Later, etc.) |
| **`Type...`** | Anywhere | **Instant Search / Filter** |
| **`R`** | System | Refresh all feeds |
| **`S`** | System | Toggle Shorts (Show/Hide) |
| **`L`** | System | Open "Watch Later" playlist |
| **`M`** | System | Mark all visible videos as seen |
| **`Q`** | System | Quit |

## ⚙️ Configuration
The application automatically creates a configuration folder at `~/.config/ytrss/`.
*   **Feeds:** stored in `ytRss.opml` (Standard OPML format).
*   **Database:** `ytrss.db` stores history and metadata.

## 📄 License
MIT

---

**⚠️ Disclaimer:** This project is created for educational purposes only. It is not intended to be used for downloading copyrighted material without permission or for violating YouTube's Terms of Service. Please use this tool responsibly.
