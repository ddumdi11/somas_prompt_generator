# SOMAS Spec — Integration des `youtube-intake-service` (Core, in-process)

> Status: **Entwurf (review-reif)** — Architektur, Packaging, Import-Reinheit,
> Erfolgs-Wire-Form (§3, 12 Felder eingefroren), O4 & O5 alle geklärt. **Vorbehalt:**
> die Fehlerpfad-Zeile (O4-Raise-Vertrag) ist zugesagt, aber noch NICHT in
> Service-Code verifiziert → CodeRabbit-PR erst nach grünem Licht von Architekt
> Youtube-Service final mergen.
> **Ersetzt** die frühere Fassung dieses Dokuments (HTTP-Sidecar + Port-Discovery);
> jene Annahme ist überholt.
> Zielversion SOMAS: **TBD** (Umbau erst NACH Service-v1.0-Tag — siehe §2).
> Rollen: Architekt Somas-App ↔ Architekt Youtube-Service, ausführend: Kurt.
> Datum: 2026-06-27

---

## 1. Ziel & Architektur-Leitlinie

Der `youtube-intake-service` ist der zentrale, wiederverwendbare YouTube-Baustein
(URL → Metadaten/Transkript/Thumbnail + SOMAS-Markdown) und ersetzt duplizierten
Extraktionscode in den Konsumenten. SOMAS ist der **erste** zu migrierende
Konsument.

**Tragende Entscheidung (Sync-Brief 2026-06-27):**

- **Core/Server-Split** im Service-Repo. **Core** = reine Logik, importierbar, KEIN
  Port / KEINE `service.info` / KEINE Shutdown-Schleife. **Server** = dünne
  FastAPI-Schicht über dem Core (bedient nur Extension/Nicht-Python-Clients).
- **SOMAS importiert den Core in-process** (`intake.process(url)`-artig), **nicht**
  den HTTP-Weg. Grund: einfaches PyInstaller-Bundling (Core als Dependency, keine
  zweite Exe, kein Daemon-Lebenszyklus, kein „Service läuft nicht"-Fall).
- **Korrektheitsregel (kritisch):** SOMAS importiert den **Core, NIEMALS den
  Server.** Ein versehentlicher Import der FastAPI-App würde einen Port binden /
  `service.info` überschreiben und mit dem laufenden Webclip-Daemon kollidieren.
- **Submodule** ist das Vehikel; SOMAS pinnt auf einen **festen Tag (v1.x)**.

---

## 2. Verbindliche Reihenfolge

Service **v1.0** fertig → als eigenständiges Repo gepusht → **getaggt** → **erst
dann** SOMAS-Submodul-Verdrahtung. Der Tag, auf den SOMAS pinnt, existiert nicht
vor dem v1.0-Tag.

> **Hold:** Bis zum v1.0-Tag werden in SOMAS **keine internen Abläufe** angefasst.
> Dieses Dokument ist Planung, kein Eingriff.

Service-v1.0-DoD liegt auf der Youtube-Service-Seite (Dauer: rohe Sekunden im JSON,
human-friendly im Markdown; `status`/`errors` härten; `.gitignore` + `service.info`-
Beispiel + API-Tests; Port-Konflikt-Feedback 51283–51300; PyInstaller-Build +
Exe-Smoke-Test; git init + push + tag). Hier nur referenziert, nicht dupliziert.

---

## 3. Core-API-Kontrakt

> Wire-Form **eingefroren** (Architekt Youtube-Service, 2026-06-27): Erfolgs-dict
> mit **12 Feldern in dieser Reihenfolge**, kanonisch und ab jetzt unverändert.
> SOMAS mappt **direkt aus dem dict** — keine `IntakeResult`-Dataclass nötig.

```text
intake.process(url: str, language: str = "de") -> dict   # NUR Erfolg/Teilerfolg
# Harte Fehler werden GERAISED (keine Fehler-dicts) → siehe O4 unten.
```

| # | Core-dict-Feld | Typ | SOMAS-Mapping |
| - | -------------- | --- | ------------- |
| 1 | `status` | str | `complete` \| `metadata_only` (in-process NIE `error` → wird geraised) |
| 2 | `transcript_available` | bool | **das** „hat Transkript?"-Signal — hierüber prüfen, NICHT über `transcript == ""` |
| 3 | `title` | str | `VideoInfo.title` |
| 4 | `channel` | str | `VideoInfo.channel` |
| 5 | `duration` | int (Sek.) | `VideoInfo.duration` |
| 6 | `duration_formatted` | str | informativ (SOMAS rechnet via `VideoInfo.duration_formatted`) |
| 7 | `url` | str | `VideoInfo.url` |
| 8 | `thumbnail_url_maxres` | str | einziges Thumbnail-Feld |
| 9 | `transcript` | str (`""`=keins) | `VideoInfo.transcript` |
| 10 | `markdown` | str | **ungenutzt** — SOMAS baut eigenes Markdown via `export.py` |
| 11 | `warnings` | list | u. a. Sprach-Fallback-Hinweis (s. O5) |
| 12 | `errors` | list | leer bei Erfolg |

**Drei Korrekturen ggü. der vorherigen Tabelle (wichtig fürs Mapping):**

1. **Kein** `video_id` top-level und **keine** `thumbnail_urls`-Map — nur
   `thumbnail_url_maxres`. SD/HQ-Varianten baut SOMAS weiter selbst via
   `build_thumbnail_urls`; die dafür nötige **Video-ID leitet SOMAS selbst aus
   `url` ab** (bestehendes `extract_video_id`), der Core liefert sie nicht.
2. **„Kein Transkript" über `transcript_available` (bzw. `status`), NICHT** über die
   Leerheit des `transcript`-Strings — der ist `""` (nicht `None`), `status`/
   `transcript_available` sind das verlässliche Signal.
3. Der **Fehler-Body** (4 Felder: `status`, `error_code`, `detail`, `errors`, inkl.
   FastAPI-`detail`) ist **nur** für die Comet-Extension (HTTP) relevant. SOMAS
   bekommt in-process eine **Exception**, nicht diesen Body.

**Fehlerpfad (O4) — Vertrag, ⚠ pending Verifikation im Service-Code:** Harte Fehler
werden als typisierte Exceptions geworfen, die der Adapter aus `youtube_intake_core`
importiert:

```text
IntakeError(Exception)            # .error_code, .message
 ├─ InvalidURLError               # error_code="invalid_url"       (ohne Netz erkennbar)
 └─ VideoUnavailableError         # error_code="video_unavailable" (yt-dlp: video weg)
unerwartet → IntakeError(error_code="processing_failed")
```

Teilerfolg („Video geholt, kein Transkript") ist **kein** Fehler → dict mit
`status="metadata_only"`. Dieser Raise-Vertrag ist von Architekt Youtube-Service
zugesagt, aber im Service-Branch noch nicht verifiziert (er wird im O4-Durchgang
nachgezogen) — daher Erfolgsfelder festzurren, **Fehlerpfad-Zeile als „pending
O4-Landing" markieren**, PR erst nach grünem Licht final mergen.

---

## 4. SOMAS-seitige Integration (Skizze)

### 4.1 Submodul + Import  ✓ bestätigt
- Service-Repo als Submodul hinzufügen, auf v1.x-Tag gepinnt. ⟨URL/Tag TBD⟩
- **Packaging (bestätigt):** Core ist ein echtes installierbares Paket
  (`pyproject`). SOMAS zieht per **`pip install ./<submodul>`** ausschließlich den
  Core; FastAPI/uvicorn stecken im **`[server]`-Extra** und kommen bei SOMAS gar
  nicht erst mit.
- **Import-Reinheit (bestätigt, strukturell erzwungen):** Da SOMAS ohne `[server]`
  installiert, ist FastAPI im SOMAS-Venv schlicht **nicht vorhanden** — die „nie den
  Server"-Regel ist damit nicht mehr versehentlich brechbar. (Service-Seite sichert
  es zusätzlich per Subprozess-Test ab.) Hinweis: aktueller Core ist VOR dem Split
  noch nicht rein — gilt erst ab dem Split/v1.0.

### 4.2 Neuer dünner Wrapper in SOMAS
`src/core/intake_adapter.py` (Name TBD), ohne PyQt-Abhängigkeit:

```text
from youtube_intake_core import process, IntakeError   # (+ Subklassen bei Bedarf)

def process_url(url, language="de") -> VideoInfo:
    try:
        d = process(url, language=language)
    except IntakeError as e:        # invalid_url | video_unavailable | processing_failed
        raise IntakeFailed(e.error_code, e.message)   # SOMAS-eigener Fehlertyp
    return VideoInfo(
        title=d["title"], channel=d["channel"],
        duration=d["duration"], url=d["url"],
        transcript=d["transcript"],            # "" wenn keins
    )
    # „kein Transkript" am Aufrufort über d["transcript_available"] / d["status"]
    #  == "metadata_only" erkennen — NICHT über transcript == "".
    #  Video-ID für Thumbnails: extract_video_id(d["url"]) (Core liefert keine).
```

- Kapselt Core-Aufruf + Feld-Mapping (§3) an EINER Stelle.
- `IntakeError` (typisiert, mit `error_code`) → differenzierte GUI-`QMessageBox`
  (ungültige URL vs. Video nicht verfügbar vs. unerwartet).
- `status`/`transcript_available` reicht der Adapter mit durch (z.B. via
  Rückgabe-Tupel oder einem schlanken Resultobjekt), damit der Aufrufer den
  „nur Metadaten / kein Transkript"-Hinweis setzen kann.

### 4.3 Router + Fallback während der Migration
Am bestehenden YouTube-Pfad (heute `get_video_info(url)`):

```text
def resolve_video_info(url, *, use_core: bool) -> VideoInfo:
    if use_core:
        try:
            return intake_adapter.process_url(url)
        except CoreUnavailable:      # Import-/Build-Problem → Fallback
            pass
    return get_video_info(url)        # bestehende In-Process-YouTube-Logik
```

> Übergangs-Designentscheidung: Solange der alte Pfad existiert, dient er als
> Sicherheitsnetz. **Nach** verifiziertem Core-Build in die SOMAS-Exe darf die alte
> direkte-YouTube-Funktionalität (`yt-dlp`/`youtube-transcript-api` in
> `youtube_client.py`) vollständig zurückgebaut werden (eigener Schritt, §6).

### 4.4 PyInstaller-Bundling
- Der Core liegt als normal installiertes Paket im SOMAS-Venv (kein Pfad-Import) →
  PyInstaller greift ihn wie jede Dependency. Prüfen: bringt der Core eigene
  Daten-Dateien mit (z.B. Markdown-Templates), die als `--add-data`/hidden-imports
  gebündelt werden müssen? Exe smoke-testen (eine echte URL → `VideoInfo`).

---

## 5. Koexistenz-Fußnoten (Hygiene, kein Absturzrisiko)
- **Webshare-Proxy ist v1.1+, NICHT v1.0** (Korrektur Architekt Youtube-Service):
  Stand real existiert noch KEINE Proxy-Logik. Da SOMAS erst nach dem v1.0-Tag
  integriert, darf zum Integrationszeitpunkt **keine** Proxy-/Env-Var-Annahme
  vorausgesetzt werden — v1.0 kennt diese Env-Vars nicht. Die folgende Notiz ist
  rein **vorausschauend** für den Fall, dass Proxy-Support (v1.1+) später ankommt:
  Daemon + SOMAS würden sich dann dieselben Credentials und damit ein Rate/Quota-
  Kontingent teilen (bei aktuellem Volumen irrelevant).
- Falls der Core Dateien rauslegt (Thumbnails/Cache): pro Video-ID benennen und
  atomar schreiben, damit parallele Läufe (Daemon ↔ SOMAS) sich nicht überschreiben.

**Ops (greift erst ab v1.1):** Keine Proxy-Credentials ins Git (Webshare nur via
Env-Vars + `.env.example` + README-Hinweis).

---

## 6. Migrations-/Rollout-Schritte (NACH v1.0-Tag)
1. Submodul hinzufügen + auf Tag pinnen; Import-/Packaging-Form festlegen (Punkt 2).
2. `intake_adapter.py` + Mapping gemäß finalem Core-Kontrakt (Punkt 1).
3. Router + Fallback verdrahten; headless gegen echte URL testen.
4. PyInstaller-Build mit Core; Exe-Smoke-Test.
5. **Erst nach Verifikation:** Alt-YouTube-Code in SOMAS zurückbauen.
6. Tests, README/CLAUDE.md-Changelog, Spec-Status auf „umgesetzt".

---

## 7. Bewusst NICHT in dieser Phase
- Comet-Extension (komplett separat, eigener Ort, reiner HTTP-Client — **nicht**
  in SOMAS und **nicht** ins Service-Repo).
- SOMAS-Interna anfassen, bevor Service v1.0 getaggt ist.
- WordPress-Integration (zweiter Konsument, später).

---

## 8. Offene Fragen (an Architekt Youtube-Service)
- ~~**O1** — Form/Signatur von `intake.process`~~ **✓ geklärt:** dict-Form,
  `duration` int + `duration_formatted` str, Mapping aus dict, keine Dataclass.
  Verbleibt nur: **exakte Schlüsselnamen** ⟨Kurts Liste⟩ → §3 final.
- ~~**O2** — Packaging~~ **✓ geklärt:** installierbares Paket (`pyproject`),
  `pip install ./<submodul>` zieht nur Core; FastAPI im `[server]`-Extra.
- ~~**O3** — Import-Reinheit~~ **✓ geklärt:** strukturell via Weglassen von
  `[server]` (FastAPI nicht im Venv) + Subprozess-Test; rein ab Split/v1.0.
- ~~**O4** — Fehlerverhalten~~ **✓ geklärt (Vertrag, ⚠ Code-Verifikation ausstehend):**
  harte Fehler (ungültige URL, nicht verfügbares Video) → typisierte **Exception**
  mit `error_code` (`IntakeError`/`InvalidURLError`/`VideoUnavailableError` aus
  `youtube_intake_core`); Teilerfolg (kein Transkript) → **dict** mit
  `status="metadata_only"`. Raise-Vertrag im Service-Branch noch nicht verifiziert
  → §3-Fehlerpfad „pending O4-Landing", PR erst nach grünem Licht final.
- ~~**O5** — Sprach-Fallback~~ **✓ geklärt:** bleibt im **Core** (angefragt → en →
  erste verfügbare). Bei Sprachabweichung schreibt der Core einen Eintrag in die
  bestehende `warnings`-Liste (kein neuer Schlüssel) — SOMAS kann daraus „nur auf
  Englisch verfügbar" anzeigen. Strukturiertes `transcript_language`-Feld wäre eine
  additive **v1.1**-Nettigkeit, bewusst nicht v1.0.
