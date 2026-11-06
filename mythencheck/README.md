# Der Mythencheck

Interaktive Web-App im Apple-Stil: 35 verbreitete Verschwörungsmythen im Faktencheck
(Wissenschaft, Gesundheit, Geschichte und NS-Revisionismus, Staat und Demokratie, „geheime Mächte“).
Zu jedem Thema: die Behauptung, ihr Hintergrund, ein eventueller wahrer Kern, belegte Fakten,
Quellen (Studien, Behörden, Gerichte, Fachbücher, Qualitätsmedien) und ein Quiz mit drei Fragen.
Dazu ein gemischtes Schnellquiz und ein lokal gespeicherter Lernfortschritt.

Stand der Recherche: November 2026.

## Öffnen

`index.html` direkt im Browser öffnen. Keine Abhängigkeiten, keine Datenübertragung;
der Quiz-Fortschritt liegt nur im `localStorage` des Browsers.
Direktlinks: `index.html#<thema-id>` (z. B. `#chemtrails`) oder `#schnellquiz`.

## Inhalte bearbeiten

- `src/data1.js`, `src/data2.js`, `src/data3.js`: alle Inhalte. Bei Quizfragen ist die erste
  Antwortoption immer die richtige, die Reihenfolge wird zur Laufzeit gemischt.
- `src/app.js`, `src/app.css`, `src/shell.html`: Logik, Gestaltung, Seitenstruktur.

Prüfen und neu bauen:

```bash
cd mythencheck/src
node validate.js                       # Struktur, IDs, 4 Optionen pro Frage, URLs, keine Gedankenstriche
python3 build.py ../artifact.html ../index.html
```
