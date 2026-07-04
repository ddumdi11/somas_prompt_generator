# Startprompt für Kurt (Claude Code) — WordPress-Beitragsbild (YouTube-Thumbnail als featured image)

> Kleiner, abgegrenzter Feature-Zuwachs auf der bestehenden WordPress-Anbindung. Kontext: Der
> End-to-End-Test (Entwurf senden) läuft grün, Formatierung passt — aber das **YouTube-Thumbnail
> fehlt** im Beitrag. Es war schlicht nicht mitgeplant: Die App baut die Thumbnail-URL für den
> Markdown-Export bereits (`build_thumbnail_urls`), reicht sie aber nicht in den WordPress-Pfad.
> PO-Entscheidung (Thorsten): als **echtes Beitragsbild (featured image)**, nicht inline.

---

Du bist der **Programmierer** im SOMAS-Team. Ergänze die WordPress-Anbindung um ein **Beitragsbild**:
Das YouTube-Thumbnail des analysierten Videos wird in die WP-Mediathek hochgeladen und als
`featured_media` am Beitrag gesetzt. Arbeite in kleinen, nachvollziehbaren Schritten; halte am Ende
für die PO-Abnahme (echter Sende-Test) inne.

## Ausgangslage (verifiziert)
- Thumbnail-URLs existieren: `src/core/youtube_client.py` → `extract_video_id(url)` und
  `build_thumbnail_urls(video_id)` → dict `{"maxres", "hq", "sd"}` (JPEG unter `i.ytimg.com`).
  Genutzt in `export.py` (mit `is_youtube`-Check) und `comparison_worker.py`.
- Sende-Pfad: `main_window._on_send_to_wordpress` (~Z.1495) → `WordPressSendDialog(result,
  suggested_title)` → (Worker) → `publish_post(...)` (`wordpress_client.py:444`) → `markdown_to_html`
  + `resolve_terms` + `WordPressClient.post(...)` (`:360`).
- **Lücken:** (1) der Dialog bekommt **kein** `video_info`/Thumbnail; (2) `post()` und `publish_post()`
  kennen **kein** `featured_media`; es gibt **keine** Media-Upload-Methode.

## Umsetzung (Reihenfolge)

### PR 1 — Media-Upload + featured_media im Client
`src/core/wordpress_client.py`:
- Neue Methode `WordPressClient.upload_media(image_bytes: bytes, filename: str, mime: str =
  "image/jpeg") -> int`: `POST` auf `self._endpoint("media")` mit Headern
  `Content-Disposition: attachment; filename="{filename}"` und `Content-Type: {mime}`, Body = rohe
  Bytes, `auth=self._auth`. Gibt die numerische Media-`id` zurück. Fehlerbehandlung analog `post()`
  (HTTPError → `WordPressError` mit Detail, inkl. 401/403 = fehlende `upload_files`-Rechte).
- `post(...)`: Parameter `featured_media: Optional[int] = None` ergänzen; wenn gesetzt,
  `payload["featured_media"] = featured_media`. Sonst unverändert.

### PR 2 — publish_post lädt das Thumbnail (nicht-fatal)
`src/core/wordpress_client.py`, `publish_post(...)`:
- Neuer Parameter `featured_image_url: Optional[str] = None`.
- Wenn gesetzt: Bild-Bytes laden (`requests.get`, Timeout `_REQUEST_TIMEOUT`) mit **Fallback**
  maxres → hq → sd (der Aufrufer übergibt idealerweise die maxres-URL; bei 404/Fehler die nächste
  probieren — oder alle drei als Liste übergeben und hier durchprobieren). Dann
  `client.upload_media(...)` → `media_id`, und `client.post(..., featured_media=media_id)`.
- **Nicht fatal:** Schlägt Laden/Upload fehl, wird der Beitrag **trotzdem** ohne Beitragsbild
  gepostet + eine Warnung geloggt/zurückgegeben (der Text ist wichtiger als das Bild). Kein Abbruch.
- Dateiname z.B. `somas-thumbnail-{video_id}.jpg`.

### PR 3 — Thumbnail-URL bis zum Dialog durchreichen + Checkbox
- `main_window._on_send_to_wordpress` (~Z.1504): aus `self.video_info` die Thumbnail-URL ableiten
  (`extract_video_id(video_info.url)` → `build_thumbnail_urls`), an den Dialog übergeben. Kein
  Video/keine Video-ID (Transkript-Modus) → `None`.
- `WordPressSendDialog.__init__`: Parameter `thumbnail_url: Optional[str] = None` (oder das
  `{maxres,hq,sd}`-dict) aufnehmen.
- Im Optionen-Bereich eine **Checkbox** „Thumbnail als Beitragsbild verwenden":
  - Vorhandene Thumbnail-URL → Checkbox sichtbar und **standardmäßig aktiv**.
  - Kein Thumbnail (Transkript) → Checkbox **deaktiviert/ausgeblendet** (kein Bild, kein Fehler).
- Beim Senden: ist die Checkbox aktiv, `featured_image_url` an `publish_post` durchreichen; sonst
  `None`.

## Harte Constraints / Hinweise
- **Body-Inhalt bleibt unverändert** — das Thumbnail ist *nur* Beitragsbild, kein Inline-Bild.
- **Transkript-Modus** (kein YouTube) muss sauber ohne Thumbnail durchlaufen.
- Rechte: der WP-User braucht `upload_files` (Autor/Admin) — bei 401/403 nicht abstürzen, sondern
  ohne Bild posten + verständliche Warnung.
- Bekannte, akzeptierte Einschränkung (v1): wiederholtes Senden lädt das Bild erneut hoch (mögliche
  Media-Dubletten). Dedup (vorhandene Media per Suche wiederverwenden) ist **später**, nicht jetzt.
- Zeilenenden bewahren, keine Voll-Reformatierung (CRLF-Churn, kein `.gitattributes`).

## Definition of Done
- Freddy-Testvideo als **Entwurf** senden → in WP erscheint das YouTube-Thumbnail als
  **Beitragsbild** (in der Beitragsliste-Spalte und in der Beitragsansicht/Theme-Vorschau).
- Transkript-Analyse senden → Beitrag ohne Beitragsbild, kein Fehler, Checkbox war deaktiviert.
- Tests: `upload_media` baut den Request korrekt (gemockt), `post()` nimmt `featured_media` in den
  Payload, `publish_post` lädt Thumbnail + reicht `media_id` weiter, Transkript-/Fehlerfall
  (Upload schlägt fehl) posten trotzdem den Text. Bestehende WP-Tests grün.
- **Doku nachziehen** (steht ohnehin aus): WordPress-Anbindung in CLAUDE.md (eigene Phase) + README
  ergänzen — inkl. dieses Beitragsbild-Zuwachses und der App-Passwort-/Wordfence-Voraussetzung.

## Arbeitsweise
Bei Unklarheit/Widerspruch erst den PO (Thorsten) fragen. Eigener kleiner PR, unabhängig von der
Anthropic-Modellpflege. Nach Fertigstellung innehalten — der reale Sende-Test ist die Abnahme.
