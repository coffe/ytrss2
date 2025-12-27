# Projekt: YT-RSS Discovery (Feeder till QuickTube)

## 1. Överblick
Ett lättviktigt CLI-program som fungerar som en "Discovery"-modul för YouTube-innehåll. Programmet hämtar metadata via RSS, presenterar en lista över nya videor och delegerar uppspelning/nedladdning till QuickTube.

Filosofi: Unix-filosofin – Gör en sak bra och koppla ihop med andra verktyg.

## 2. Nuvarande Status (Implementerat 2025-12-20)
Programmet är nu fullt fungerande med följande funktioner:

*   **Asynkron Hämtning:** Använder `asyncio` och `aiohttp` för att hämta alla RSS-flöden parallellt.
*   **Prenumerationshantering:** Läser och skriver kanaler till `ytRss.opml`. Stöd för att lägga till och ta bort kanaler direkt i UI:t.
*   **Databas:** SQLite (`ytrss.db`) används för att:
    *   Markera videor som **[SEDD]**.
    *   Cacha videolängder (`duration`) för snabbare laddning.
*   **Metadata & Längd:** Hämtar videolängd i bakgrunden via `yt-dlp` (asynkront med semaphore-begränsning).
*   **TUI (Text User Interface):** Byggt med `simple-term-menu`.
    *   Navigering med piltangenter.
    *   Sök/Filtrering genom att skriva direkt i menyn.
    *   Visar kanalnamn, tid, längd och Shorts-markering.
*   **Shorts-detektering:** Markerar automatiskt videor < 61 sekunder eller med `#shorts`-taggar.
*   **QuickTube Integration:** Kopierar vald video-URL till systemets urklipp (`wl-copy`) och startar `quicktube`.

## 3. Teknisk Stack
*   **Språk:** Python 3.13+
*   **RSS-Parsing:** `feedparser`
*   **Nätverk:** `aiohttp` (Asynkront HTTP)
*   **UI:** `simple-term-menu`
*   **Databas:** `sqlite3` (Inbyggt)
*   **Externa Beroenden:** `yt-dlp` (för metadata), `quicktube` (för uppspelning), `wl-copy` (för urklipp).

## 4. Arbetsflöde
1.  **Start:** Läser in `ytRss.opml` och startar asynkron hämtning av flöden.
2.  **Meny:** Visar en huvudmeny med alla kanaler + "Alla videor (Mix)".
3.  **Lista:** Visar videor sorterade på datum.
    *   Hämtar videolängd i bakgrunden om det saknas.
4.  **Val:** Användaren väljer video -> URL kopieras till clipboard -> `quicktube` startas.
5.  **Historik:** Videon markeras som sedd i databasen.

## 5. Att-göra / Framtida förbättringar
- [x] Databas: Spara ID på videor som redan visats.
- [x] OPML-import/export: Fullt stöd via `ytRss.opml`.
- [x] UI: TUI med piltangenter (`simple-term-menu`).
- [x] Shorts-detektering: Markeras i listan.
- [ ] **Shorts-filter:** Möjlighet att *dölja* Shorts helt från listan (toggle).
- [ ] **Konfigurationsfil:** Flytta hårdkodade sökvägar (DB, OPML) till en config.ini eller liknande.