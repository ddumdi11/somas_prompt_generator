# Startprompt für Kurt (Claude Code) — Anthropic-Modelle aktualisieren

> Kleiner, abgegrenzter Zwei-Datei-Change (kein eigenes Spec-Dokument). Kontext: die App
> exponiert bei **Anthropic direkt** noch `claude-opus-4-6` / `claude-sonnet-4-6` / Haiku 4.5;
> der aktuelle Anthropic-Stand ist Fable 5 / Opus 4.8 / Sonnet 5 / Haiku 4.5. Analog zur
> Perplexity-Aktualisierung in v0.10.1. Modell-IDs & Preise sind vom Architekten gegen die
> offizielle Doku verifiziert (Stand 2026-07-02).

---

Du bist der **Programmierer** im SOMAS-Team. Aktualisiere die **Anthropic-Direkt-Modellliste**.
Vom PO (Thorsten) freigegeben: **6 Modelle anbieten** (die 4 aktuellen **plus** die beiden 4.6er
als Kontinuität), **Default bleibt `claude-sonnet-4-6`**.

## Zwei Stellen — synchron halten
1. `src/core/anthropic_client.py` — `MODELS: ClassVar[list[dict[str, str]]]` (~Z.21–37).
2. `src/config/api_providers.json` — Provider-Objekt `"id": "anthropic"`, Feld `models`
   (+ `default_model`).

Beide Listen müssen **identisch** sein (IDs, Namen, Reihenfolge). `default_model` bleibt
`claude-sonnet-4-6`.

## Zielliste (exakt diese IDs — pinned Snapshots, verifiziert gegen platform.claude.com)

| Reihenfolge | `id` | `name` | `description` |
| --- | --- | --- | --- |
| 1 | `claude-fable-5` | `Claude Fable 5` | `Flaggschiff – höchste Leistung, langsam & am teuersten` |
| 2 | `claude-opus-4-8` | `Claude Opus 4.8` | `Sehr leistungsstark – komplexe Analysen` |
| 3 | `claude-sonnet-5` | `Claude Sonnet 5` | `Neu – beste Balance aus Tempo und Intelligenz` |
| 4 | `claude-sonnet-4-6` | `Claude Sonnet 4.6` | `Balanciert – bewährt/empfohlen für SOMAS (Default)` |
| 5 | `claude-opus-4-6` | `Claude Opus 4.6` | `Stark – bisheriges Flaggschiff (Vorgänger)` |
| 6 | `claude-haiku-4-5-20251001` | `Claude Haiku 4.5` | `Schnell & günstig – für kurze Inhalte` |

- `claude-haiku-4-5-20251001` ist **unverändert** aktuell (Alias `claude-haiku-4-5`) — ID so
  belassen.
- Entfernt wird **nichts** ersatzlos: Opus 4.6 und Sonnet 4.6 **bleiben** in der Liste (PO-Wunsch).
- Falls `create_client()` / Modellvergleich / Verifikations-Picker die Liste über
  `get_available_models()` beziehen: keine weitere Änderung nötig, sie erben die neue Liste
  automatisch. Kurz gegenprüfen, dass kein weiterer Ort Anthropic-IDs hartkodiert.

## Kontext-Notizen (nicht einbauen, nur zur Einordnung)
- Standardpreise $/MTok (In/Out): Fable 5 = 10/50 · Opus 4.8 = 5/25 · Sonnet 5 = 2/10
  (Einführung bis 31.08.2026, danach 3/15) · Sonnet 4.6 = 3/15 · Opus 4.6 = 5/25 · Haiku 4.5 = 1/5.
  Die App zeigt für Anthropic **keine** Preise an (nur `id/name/description`) — also **keine**
  Preisfelder ergänzen.
- Fable 5 / Opus 4.8 / Sonnet 5 nutzen einen neuen Tokenizer (~30 % mehr Tokens pro Text);
  Sonnet 4.6 (Default) nutzt den alten — daher bleibt das `DEFAULT_MAX_TOKENS`-Verhalten für den
  Default unverändert. Kein Handlungsbedarf, nur bewusst so.
- Anthropic direkt bleibt `supports_web_search: false` — für die **Verifikation** (Stufe 2) bleibt
  die Empfehlung ein web-fähiges Modell (Perplexity Sonar). Nichts ändern.

## Optional (nur wenn schnell & sicher verifizierbar)
Im **OpenRouter**-Provider-Block von `api_providers.json` stehen als Fallback noch ältere
Anthropic-Slugs (`anthropic/claude-sonnet-4.5`, `anthropic/claude-opus-4.5`,
`anthropic/claude-3.5-haiku`). OpenRouter lädt Modelle dynamisch, daher unkritisch. Wenn du die
aktuellen OpenRouter-Slugs (z. B. `anthropic/claude-sonnet-5`, `anthropic/claude-opus-4.8`,
`anthropic/claude-fable-5`) **gegen die Live-Liste** bestätigen kannst, gern aktualisieren —
**sonst weglassen** (keine geratenen Slugs).

## Definition of Done
- Beide Listen identisch, `default_model` = `claude-sonnet-4-6`.
- App startet, Anthropic-Provider zeigt die 6 Modelle im Picker (Analyse **und**
  Verifikations-Picker), Default vorausgewählt.
- Falls es einen Modelllisten-Test gibt: anpassen; sonst optional ein Mini-Test, der prüft, dass
  `anthropic_client.MODELS` und der `anthropic`-Block in `api_providers.json` dieselben IDs
  enthalten (schützt künftig vor Auseinanderlaufen).
- `README`/`CLAUDE.md`: kurzer Hinweis, dass die Anthropic-Direktliste aktualisiert wurde
  (optional, falls dort Modelllisten dokumentiert sind).

## Constraints / Arbeitsweise
- Zeilenenden bewahren, keine Voll-Reformatierung (CRLF-Churn, kein `.gitattributes`).
- Ein eigener, kleiner PR — **unabhängig** von Increment B der Reasoning-Leak-Härtung.
- Bei Unklarheit den PO fragen. Diese Aufgabe ist bewusst klein gehalten.
