# Hur ytRss är byggt

Här är en sammanställning av de tillvägagångssätt och verktyg som använts för att utveckla ytRss.

## Verktyg (Tools)

### Programmeringsspråk
*   **Python 3**: Kärnan i applikationen.

### Bibliotek & Paket
*   **InquirerPy**: Används för att skapa interaktiva menyer och listor i terminalen (CLI/TUI).
*   **Rich**: För snygg formatering, färger och utskrifter i terminalen (paneler, tabeller, stiliserad text).
*   **Feedparser**: För att hämta och tolka RSS-flöden från YouTube.
*   **Aiohttp & Asyncio**: För asynkron och parallell hämtning av data (RSS-feeds) för att öka prestandan markant.
*   **SQLite3**: Inbyggd databas (via Python-biblioteket) för att spara historik ("sedda videos"), spellistor, videometadata och relationer.
*   **Configparser**: För hantering av konfigurationsfiler (`ytrss.conf`).
*   **JSON & XML**: För datahantering och parsing av vissa format.

### Externa Beroenden
*   **Mediaspelare (MPV/VLC)**: Applikationen delegerar uppspelning till externa spelare via systemanrop (`subprocess`), vilket ger stöd för högkvalitativ video utan att bygga en egen renderingsmotor.
*   **yt-dlp**: Används för nedladdning av videos och extrahering av strömmar.

## Tillvägagångsätt (Approaches)

### Arkitektur
*   **Modulär Struktur (Refactoring)**: Projektet har genomgått en refactoring från ett enda monolitiskt script till en modulär struktur med en `src/`-katalog innehållande specifika moduler som:
    *   `config.py`: Konfigurationslogik.
    *   `database.py`: Databasinteraktioner.
    *   `ui.py`: Gränssnittskomponenter.
    *   `player.py`: Uppspelningslogik.
    *   `downloader.py`: Nedladdningshantering.
*   **Databasdriven Design**: Persistens hanteras via en relationell databas (SQLite). Detta möjliggör funktioner som "Watch Later", multipla spellistor och effektiv spårning av sedda videos.
*   **Objektorientering**: Användning av klasser (t.ex. `ConfigManager`, `DatabaseManager`) för att inkapsla tillstånd och logik.

### Funktionalitet
*   **Asynkron Exekvering**: Tung nätverkskommunikation (hämtning av RSS-feeds) sker asynkront (`async`/`await`) för att applikationen ska kännas snabb och responsiv.
*   **Robust Konfiguration**: En "fail-safe" konfigurationshanterare som laddar standardvärden om konfigurationsfilen saknas eller är ofullständig.
*   **OPML-Standard**: Använder OPML-formatet för att lagra och läsa prenumerationer, vilket gör det enkelt att importera/exportera från andra RSS-läsare.

### Användarupplevelse (UX)
*   **Interaktiv TUI**: Istället för flaggor och argument bygger UX på interaktiva menyer där användaren navigerar med piltangenter.
*   **Säsongsbaserade Teman**: Dynamisk temahorisering (t.ex. jul, nyår) implementerat via konfiguration.
*   **Visuell Feedback**: Använder färger och ikoner (via `Rich`) för att tydligt skilja på t.ex. Shorts och vanliga videos, eller sedda och osedda objekt.
