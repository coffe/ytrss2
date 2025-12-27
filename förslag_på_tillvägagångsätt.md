# Förslag på tillvägagångssätt: Status & Framtid

Detta dokument spårar utvecklingen av funktionalitet i `ytrss`.

## ✅ GENOMFÖRT

### 1. Databasstruktur (SQLite)
*   [x] Implementerat schema för `playlists`, `videos` och `playlist_items`.
*   [x] Automatisk skapande av "Watch Later" vid start.

### 2. Backend-logik
*   [x] `add_to_playlist(playlist_name, video_obj)` - Hanterar metadata och kopplingar.
*   [x] `get_playlist_videos(playlist_name)` - Hämtar listor via JOINs.
*   [x] `remove_from_playlist(playlist_name, video_id)`.
*   [x] Konfigurerbar mediaspelare via `ytrss.conf`.

### 3. UI - Grundläggande
*   [x] Sub-meny vid val av video (Play, Watch Later, Mark Seen, etc.).
*   [x] Dynamiska menyer som reflekterar vald mediaspelare.
*   [x] Säsongsbaserade teman (Jul & Nyår).
*   [x] **Nyårstema:** Implementerat "Stardust" med nedräkning.
    *   Vald färgpalett: **Festive Red** (Röda siffror mot guldtema).
    *   Andra utvärderade alternativ:
        *   *Frosty Cyan* (Isblå siffror)
        *   *Starlight White* (Vita siffror)
        *   *Emerald Green* (Gröna siffror)

---

## 🚀 PÅGÅENDE / FRAMTIDA IDÉER

### Polering av UX
*   [ ] **Fler kortkommandon:** Möjlighet att trycka 'w' direkt i listan utan att öppna sub-menyn (kräver anpassning av `InquirerPy`).

### Statistik & Insikter
*   [x] Grundläggande statistikvy (`I` i huvudmenyn).
*   [ ] Mer avancerad analys av tittarvanor.

### Webb-gränssnitt (ytRss 3.0?)
*   [ ] Utforska möjligheten att ha en lättviktig Flask/FastAPI-server som frontend istället för TUI.
