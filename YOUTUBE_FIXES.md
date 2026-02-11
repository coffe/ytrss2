# YouTube Playback & Download Stability Fixes (2026)

This document describes the critical configurations required to make `yt-dlp` and `mpv` work reliably with YouTube's modern anti-bot protections (as of Jan 2026).

## The Problem
When attempting to stream or download videos, the following errors occur:
*   **HTTP 403 Forbidden**: YouTube rejects the connection.
*   **TLS Error**: Connection drops during handshake.
*   **"No supported JavaScript runtime found"**: `yt-dlp` fails to calculate signatures.
*   **Throttling**: Downloads start fast but drop to 0kb/s.

## The Solution: "The Golden Trio"

To guarantee stability, **all three** of the following strategies must be combined.

### 1. Force IPv4 (`--force-ipv4`)
**Why:** YouTube aggressively blocks or throttles requests from IPv6 addresses that rotate frequently (common with "Privacy Extensions" on Linux).
**Fix:** Force the connection to use IPv4.

### 2. JavaScript Runtime (`--js-runtime`)
**Why:** YouTube now requires complex JavaScript execution to generate the `n` parameter (throttling signature). Python's internal interpreter is often insufficient.
**Fix:** Explicitly tell `yt-dlp` to use an external engine like `node`, `quickjs`, or `deno`.
*   *Prerequisite:* Ensure `node` or `quickjs` is installed and in PATH.

### 3. Browser Cookies (`--cookies-from-browser`)
**Why:** YouTube blocks unauthenticated "bot-like" traffic. Using cookies from a real browser validates the request as a human user.
**Fix:** Borrow cookies from Firefox, Chrome, or Brave.

---

## Implementation Details

### A. Direct `yt-dlp` Usage
When calling `yt-dlp` directly (e.g., via `subprocess`):

```python
cmd = [
    "yt-dlp",
    "--force-ipv4",                # 1. Network Stability
    "--js-runtime", "node",        # 2. JS Engine (path to binary if needed)
    "--cookies-from-browser", "firefox",  # 3. Auth
    url
]
```

### B. Embedding in `mpv` (The Tricky Part)
`mpv` uses a hook to call `yt-dlp`. You must pass these options via `--ytdl-raw-options`.

**Critical Syntax Note:**
*   Options are comma-separated `key=value`.
*   Flags that take **no value** (like `force-ipv4`) must be passed as `key=` (with an empty value after the equals sign). If you pass `key=true`, `yt-dlp` will crash.

**Correct MPV Command Construction:**

```python
cmd = [
    "mpv",
    "--force-window",
    # Point to the specific binary
    f"--script-opts=ytdl_hook-ytdl_path={shutil.which('yt-dlp')}",
    
    # RAW OPTIONS
    # force-ipv4=  <-- EMPTY VALUE IS REQUIRED!
    # js-runtime=node
    # cookies-from-browser=firefox
    "--ytdl-raw-options=force-ipv4=,js-runtime=node,cookies-from-browser=firefox",
    
    url
]
```

## Summary Checklist for Future Agents
1.  [ ] **Check for Node/QuickJS:** `shutil.which('node')`.
2.  [ ] **Check for Browser:** Ask user or detect config.
3.  [ ] **Apply Flags:** Always apply `--force-ipv4` on Linux.
4.  [ ] **Validate MPV Syntax:** Ensure boolean flags in `raw-options` end with `=`.
