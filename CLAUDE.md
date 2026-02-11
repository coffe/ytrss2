# YTRSS 2.0 - Projektkontext

## Översikt

YTRSS är en minimalistisk YouTube RSS-klient för terminalen. Låter användare följa YouTube-kanaler via RSS utan att behöva logga in på YouTube.

## Senaste ändringar (2026-01-24)

### Fixat: mpv-uppspelning fungerade inte
**Problem:** Videos spelades inte upp korrekt via mpv.

**Orsak:** Saknade flaggor för yt-dlp-path och format-val.

**Lösning i `src/player.py`:**
```python
# Före (fungerade inte alltid):
cmd.append("--no-terminal")
cmd.append("--force-window")

# Efter (fixat):
cmd.append("--force-window")
ytdlp_path = shutil.which("yt-dlp")
if ytdlp_path:
    cmd.append(f"--script-opts=ytdl_hook-ytdl_path={ytdlp_path}")
cmd.append("--ytdl-format=bestvideo[height<=?1080]+bestaudio/best")
```

**Ändringar:**
1. Borttagen `--no-terminal` (dolde felmeddelanden)
2. Lagt till explicit yt-dlp-path via `--script-opts`
3. Lagt till `--ytdl-format` för pålitlig format-val
4. Separat format för audio-only: `bestaudio/best`

## Arkitektur

```
src/
├── config.py      # Konfigurationshantering via .conf-fil
├── database.py    # SQLite för sedda videos, spellistor, metadata
├── downloader.py  # Nedladdning med yt-dlp
├── player.py      # Uppspelning via mpv/vlc (ÄNDRAD 2026-01-24)
├── ui.py          # TUI-komponenter (Rich + InquirerPy)
└── utils.py       # Hjälpfunktioner
```

## Kända problem & vanliga fel

### mpv + yt-dlp + YouTube
- "No video or audio streams selected" - mpv kan inte välja streams
- "EDL specifies no segments" - parsing-fel efter yt-dlp-uppdatering
- HTTP 403 - YouTube blockerar, uppdatera yt-dlp med `yt-dlp -U`
- Video utan ljud - format-val fungerar inte, använd explicit `--ytdl-format`

### Lösningar
1. Uppdatera yt-dlp: `yt-dlp -U`
2. Explicit yt-dlp-path till mpv
3. Specificera format explicit

## Beroenden

- feedparser, aiohttp (RSS-hämtning)
- rich, InquirerPy (TUI)
- pyperclip (urklipp)
- Externa: yt-dlp, mpv/vlc, ffmpeg

## Relaterade projekt

Se även `/home/coffe/ai/coding/zenfeed` - Generell RSS-läsare med liknande arkitektur.
