# Förslag på nya funktioner för YTRSS 2.0

### 1. 📂 Kategorier / Taggar för Kanaler
*   **Funktion:** Möjlighet att gruppera kanaler (t.ex. "Tech", "Nyheter", "Nöje").
*   **Varför:** Om man har 50+ prenumerationer blir det rörigt. Att kunna filtrera på "Visa bara Tech-nyheter" är en viktig funktion för organisation.
*   **Implementation:** En ny tabell i databasen och en uppdatering i `src/ui.py` för att filtrera vyer.

### 2. ⬇️ Offline-läge / Auto-download [KLAR]
*   **Funktion:** En knapp för att ladda ner alla videor i "Watch Later"-listan till disken.
*   **Varför:** Perfekt för resor eller svajigt internet. Utnyttjar `yt-dlp` fullt ut.

### 3. 🖼️ Tumnaglar i terminalen (Experimentellt)
*   **Funktion:** Visa små bilder (thumbnails) bredvid videon i listan med hjälp av moderna terminal-protokoll (Kitty, iTerm2, Sixel).
*   **Varför:** Gör gränssnittet rikare och hjälper användaren identifiera innehåll snabbare.

### 4. 🧠 Smarta Spellistor (Filter)
*   **Funktion:** Skapa dynamiska spellistor baserade på regler.
    *   "Långa videos (>20 min)"
    *   "Från senaste dygnet"
    *   "Osedda videos från kanal X"
*   **Varför:** Automatisk kurering av innehåll.

### 5. 📊 Statistik-sida [KLAR]
*   **Funktion:** En vy som visar "Din vecka på YouTube".
    *   "Du har tittat på 3 timmar video"
    *   "Din favoritkanal är X"
*   **Varför:** Rolig metadata och ger liv åt Dashboarden.
