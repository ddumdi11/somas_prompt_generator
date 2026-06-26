# SOMAS Spec — Integration des `youtube-intake-service`

> Status: **Entwurf / Spezifikation** (Implementierung in eigener Phase)
> Zielversion: **TBD** (nächste Minor nach WordPress-Export)
> Autor: Architektur-Abstimmung Thorsten ↔ Claude
> Datum: 2026-06-26

---

## 1. Ziel & Motivation

Der [`youtube-intake-service`](https://github.com/ddumdi11/youtube-intake-service)
ist ein kleiner lokaler **FastAPI-Sidecar** (eigenständige `.exe`), der aus einer
YouTube-URL saubere, fertige Daten macht: Titel, Kanal, Dauer, Thumbnail und
Transkript — plus ein vorgefertigtes Markdown. Er findet selbst einen freien
Port, schreibt seine Verbindungsdaten in eine Datei und fährt nach Inaktivität
automatisch herunter.

SOMAS macht dieselbe Arbeit aktuell **in-process** in `src/core/youtube_client.py`
(via `yt-dlp` + `youtube-transcript-api`). Die Integration verschiebt diese
Verantwortung **optional** an den Sidecar. Vorteile:

- **Entkopplung** der fragilen YouTube-Abhängigkeiten (`yt-dlp` bricht häufig bei
  YouTube-Änderungen) vom GUI-Prozess — Updates am Sidecar ohne SOMAS-Release.
- **Wiederverwendung** desselben Dienstes durch andere Tools/Workflows (n8n,
  Skripte) — eine Quelle der Wahrheit für Intake.
- **Robustheit**: Sidecar-Absturz reißt die GUI nicht mit; klare
  `status`/`errors`-Felder.

**Leitprinzip:** Die Integration ist **additiv und nicht-brechend**. Der bestehende
In-Process-Pfad bleibt als **Fallback** vollständig erhalten. Kein Sidecar →
SOMAS funktioniert exakt wie heute.

---

## 2. Scope

### In Scope
- Service-Discovery (Auffinden eines laufenden Sidecars).
- HTTP-Client (`GET /process`, `GET /health`) mit Timeout/Fehlerbehandlung.
- Mapping der Service-Antwort auf das bestehende `VideoInfo`-Datenmodell.
- Fallback-Logik: Sidecar nicht erreichbar/fehlerhaft → bestehender
  In-Process-Pfad (`get_video_info`).
- Settings-Toggle: „YouTube-Intake-Service verwenden (falls verfügbar)".
- Optionaler Auto-Start des Sidecars (nur wenn Pfad zur `.exe` konfiguriert).

### Out of Scope (vorerst)
- Bündeln/Mitliefern der Sidecar-`.exe` mit SOMAS (separate Distribution).
- Ersetzen des In-Process-Pfads (bleibt dauerhaft als Fallback).
- Nutzung des vom Service gelieferten `markdown`-Felds (SOMAS baut sein Markdown
  selbst via `export.py`; siehe §6, offene Frage O3).

---

## 3. Service-Schnittstelle (Ist-Stand des Sidecars)

### Discovery
- Beim Start schreibt der Service Verbindungsdaten nach
  `~/.youtube_intake/service.info` (siehe `service.info.example` im Repo).
- Bindet an `127.0.0.1`, Port aus Bereich **51283–51300** (Auto-Discovery).
- Fährt nach Inaktivität automatisch herunter (Default-Timeout konfigurierbar
  via `--timeout` Minuten, 1–1440).

### Endpunkte
- `GET /health` → `{ "status": "ok", "timeout_in_seconds": <int> }`
  (setzt zugleich den Idle-Timer zurück → Liveness-Check).
- `GET /process?url=<youtube_url>&language=de` → siehe Felder unten.

### Antwortfelder `GET /process` (HTTP 200)
| Feld | Bedeutung | SOMAS-Mapping |
| ---- | --------- | ------------- |
| `status` | `complete` \| `metadata_only` | steuert Transkript-Handling |
| `transcript_available` | `true` / `false` | Info/Logging |
| `title` | Videotitel | `VideoInfo.title` |
| `channel` | Kanal/Uploader | `VideoInfo.channel` |
| `duration` | Dauer in **Sekunden** (roh) | `VideoInfo.duration` |
| `duration_formatted` | `MM:SS` / `H:MM:SS` | (SOMAS rechnet selbst → ignorierbar) |
| `url` | angefragte URL | `VideoInfo.url` |
| `thumbnail_url_maxres` | Max-Res-Thumbnail | (SOMAS baut Thumbnails via `build_thumbnail_urls`) |
| `transcript` | Klartext-Transkript (leer wenn keins) | `VideoInfo.transcript` |
| `markdown` | fertiges Markdown | vorerst ungenutzt (O3) |
| `warnings` | nicht-fatale Hinweise | Logging/Status |
| `errors` | leer bei Erfolg | Logging |

### Fehlerantworten
Einheitlicher JSON-Body mit passendem HTTP-Status:

| Status | `error_code` | Bedeutung |
| ------ | ------------ | --------- |
| `400` | `invalid_url` | Keine gültige YouTube-URL |
| `404` | `video_unavailable` | Video privat/entfernt/geo-blockiert |
| `500` | `processing_failed` | Unerwarteter Fehler |

---

## 4. Architektur in SOMAS

### Neue Datei: `src/core/intake_client.py`
Kapselt Discovery + HTTP. Keine PyQt-Abhängigkeit (testbar/headless).

```text
read_service_info() -> Optional[ServiceInfo]      # liest ~/.youtube_intake/service.info
is_service_healthy(info, timeout=2.0) -> bool     # GET /health
process_url(url, language="de", timeout=120)
        -> IntakeResult                            # GET /process, gemappt
to_video_info(IntakeResult) -> VideoInfo          # Mapping auf bestehendes Modell
```

- `ServiceInfo`: `host`, `port`, ggf. `pid`/`started_at` (Format gemäß
  `service.info.example` final fixieren — **O1**).
- `IntakeResult`: 1:1-Abbild der relevanten Antwortfelder + `status`/`errors`.
- Fehler werden als **typisierte Exceptions** (`IntakeUnavailable`,
  `IntakeProcessingError`) signalisiert, damit der Aufrufer sauber auf Fallback
  schalten kann.

### Integrationspunkt
Zentral dort, wo SOMAS heute `get_video_info(url)` ruft (YouTube-Pfad im
`main_window` bzw. der zuständige Worker). Vorgeschlagene **Router-Funktion** in
`youtube_client.py` oder neuer dünner Wrapper:

```text
def resolve_video_info(url, *, prefer_service: bool) -> VideoInfo:
    if prefer_service:
        info = read_service_info()
        if info and is_service_healthy(info):
            try:
                return to_video_info(process_url(url))
            except IntakeProcessingError:
                # 404/400: echtes inhaltliches Problem → NICHT blind weiterfallen,
                #          dem Nutzer melden (sonst doppelte Fehlversuche).
                raise
            except IntakeUnavailable:
                pass  # Netzwerk/Timeout → Fallback
    return get_video_info(url)   # bestehender In-Process-Pfad
```

> Designentscheidung **D1**: Bei **inhaltlichen** Fehlern (400/404) NICHT auf den
> In-Process-Pfad zurückfallen (würde nur denselben Fehler langsamer
> reproduzieren). Nur bei **Erreichbarkeits**-Problemen (kein `service.info`,
> `/health` rot, Timeout, Connection-Refused) Fallback.

---

## 5. GUI / Settings

- Neue Checkbox in `settings_dialog.py` (Gruppe „YouTube-Intake"):
  **„YouTube-Intake-Service verwenden, wenn verfügbar"** (Default: **aus**,
  damit Bestandsverhalten unverändert bleibt, bis bewusst aktiviert).
- Persistenz analog bestehender Prefs (`user_preferences.json`,
  `load_preferences`/`save_preferences`), Key z.B. `use_intake_service`.
- Optionales Feld **„Pfad zur Service-.exe"** für Auto-Start (**O2**); leer =
  kein Auto-Start, nur Nutzung eines bereits laufenden Sidecars.
- Status-Label „Service erreichbar / nicht erreichbar" mit Test-Button
  (analog WordPress-Test, asynchron via Worker — kein GUI-Freeze).

---

## 6. Fehler- & Edge-Cases

- **Kein `service.info`** → Service gilt als nicht vorhanden → Fallback.
- **`service.info` vorhanden, aber Port tot** (Service beendet) → `/health`
  schlägt fehl → Fallback. (Stale-Info nicht als hart fatal behandeln.)
- **`metadata_only`** (kein Transkript) → `VideoInfo.transcript = ""`; SOMAS
  verhält sich wie heute bei fehlendem Transkript (Tab/Hinweise unverändert).
- **Timeout** beim `/process` (langes Video) → konfigurierbares Timeout
  (Default 120 s, wie In-Process); bei Überschreitung Fallback + Hinweis.
- **Sprache**: SOMAS reicht die gewählte Sprache als `language`-Param durch
  (Default `de`).
- **Idle-Shutdown**: Vor jedem `/process` ein `/health` (setzt Timer zurück)
  ODER direkt `/process` und bei Connection-Refused einmal Auto-Start versuchen
  (falls `.exe`-Pfad gesetzt).

---

## 7. Tests

- `tests/test_intake_client.py` (vollständig offline, HTTP **gemockt**):
  - `read_service_info`: vorhanden / fehlt / korrupt.
  - `is_service_healthy`: ok / Timeout / Connection-Refused.
  - `process_url` Mapping: `complete`, `metadata_only`, 400/404/500.
  - `to_video_info`: Felder korrekt gemappt (Sekunden, leeres Transkript).
  - Router `resolve_video_info`: Service-aus / Service-an-gesund /
    Service-an-tot → korrekter Pfad bzw. Fallback; D1 (kein Fallback bei 404).
- Kein echter Netz-/Sidecar-Zugriff in der CI (wie beim Service-Repo selbst).

---

## 8. Offene Fragen (vor Implementierung klären)

- **O1 — `service.info`-Format:** Exaktes Format aus `service.info.example`
  übernehmen (Key/Value? JSON? nur `host:port`?). Quelle: Service-Repo.
- **O2 — Auto-Start ja/nein:** Soll SOMAS den Sidecar bei Bedarf selbst starten
  (konfigurierter `.exe`-Pfad) oder nur einen **bereits laufenden** Dienst
  nutzen? (Auto-Start = mehr Komfort, aber Prozess-Lifecycle-Verantwortung.)
- **O3 — `markdown`-Feld nutzen?** Service liefert fertiges Markdown. SOMAS baut
  sein Markdown jedoch selbst (Header, Thumbnail, SOMAS-Block via `export.py`).
  Vorschlag: Service-`markdown` **ignorieren**, nur strukturierte Felder nutzen
  (Konsistenz mit Modellvergleich/Einzelexport).
- **O4 — Distribution:** Wird die `.exe` später mit SOMAS gebündelt oder bleibt
  sie getrennt installierbar? (Beeinflusst Settings-UX und Docs.)
- **O5 — Sprache/Transkript-Auswahl:** Reicht der einzelne `language`-Param, oder
  braucht SOMAS später mehrsprachige Fallbacks (de→en), wie heute in
  `get_transcript`?

---

## 9. Umsetzungsschritte (Phasen-Skizze)

1. `intake_client.py` + Datenklassen + Mapping (headless, getestet).
2. Router `resolve_video_info` + Verdrahtung am bestehenden YouTube-Pfad.
3. Settings-Toggle + Status/Test (asynchron).
4. (Optional, O2) Auto-Start des Sidecars.
5. Tests, README/CLAUDE.md-Changelog, Spec-Status auf „umgesetzt".
