# UI-Redesign Spec: Collapsible Sections + Transkript-Brücke (v0.4.1)

> **Entwicklungsanweisung für Claude Code**
>
> Erstellt von: Claude.ai (Architekt) · Genehmigt von: Thorsten (PO)
> Datum: 2026-02-06
> Kontext-Mockup: `SOMAS_UI_Redesign_Konzept.html` (Option A)

---

## 🎯 Problem

Bei Standard-Fenstergröße (800×700, definiert in `_setup_ui`) beanspruchen die Sektionen
META-INFORMATIONEN (`_create_meta_section`) und Zeitbereich (`_create_time_range_section`)
zusammen ca. 250px vertikalen Platz — auch wenn der Nutzer sie nach dem Laden nicht mehr braucht.
Dadurch sind FRAGEN, Variante, Provider und Generate-Button kaum noch sichtbar.

Zusätzlich: Wenn `get_video_info()` in `youtube_client.py` ein Transkript holt, gibt es aktuell
keinen Weg, dieses im Tab "Manuelles Transkript" einzusehen oder zu editieren.

---

## 📋 Lösung: 6 Schritte

### Schritt 1: CollapsibleSection-Widget (neue Datei)

**Datei:** `src/gui/collapsible_section.py`

Ein wiederverwendbares Widget mit klickbarem Header und ein-/ausklappbarem Body.

```python
class CollapsibleSection(QWidget):
    """Einklappbare Sektion mit kompakter Header-Zusammenfassung."""

    # Signals
    toggled = pyqtSignal(bool)  # True = expanded

    def __init__(self, title: str, parent=None):
        super().__init__(parent)
        # Header-Zeile: [▶/▼] [Titel] [--- Zusammenfassung rechts ---]
        # Body-Bereich: beliebiges QWidget, per show/hide toggle

    def set_summary(self, text: str):
        """Kompakter Text im Header rechts (z.B. '✓ Titel · Kanal · 15:32')."""

    def set_content_widget(self, widget: QWidget):
        """Setzt das Widget im aufklappbaren Body."""

    def expand(self) -> None: ...
    def collapse(self) -> None: ...
    def is_expanded(self) -> bool: ...
```

**Visuelles Design (orientiert am PyQt6-Standard-Look):**
- Header: Hintergrund `#E8E8E8`, Hover `#DDD`, Padding 6px 10px
- Pfeil: `▶` (zu) / `▼` (offen), Farbe `#666`, Font-Size 10px
- Titel: Font-Weight 500, Font-Size 12px
- Zusammenfassung: Font-Size 11px, Farbe `#2E7D32` (grün) bei Daten vorhanden, `#888` bei inaktiv
- Body: Weißer Hintergrund, 1px Border-Top `#C0C0C0`
- Gesamt: 1px Border `#C0C0C0`, Border-Radius 4px
- Kein Animation nötig — einfaches `setVisible(True/False)` auf den Body reicht

---

### Schritt 2: Metadaten-Sektion umbauen

**Betrifft:** `main_window.py` → `_create_meta_section()` und `_setup_ui()`

**Aktuell (Zeile 203–223):**
```python
def _create_meta_section(self) -> QFrame:
    frame = QFrame()
    # ... QLabel("META-INFORMATIONEN") + self.meta_text (QTextEdit, maxHeight=100)
    return frame
```

**Neu:** Ersetze `QFrame` durch `CollapsibleSection`:
```python
def _create_meta_section(self) -> CollapsibleSection:
    self.meta_section = CollapsibleSection("Quellen-Informationen")
    # Body: der bisherige QTextEdit für editierbare Metadaten
    content = QWidget()
    layout = QVBoxLayout(content)
    self.meta_text = QTextEdit()
    self.meta_text.setMaximumHeight(100)
    self.meta_text.setPlaceholderText("Metadaten werden hier angezeigt...")
    layout.addWidget(self.meta_text)
    self.meta_section.set_content_widget(content)
    return self.meta_section
```

**In `_display_meta()` (Zeile 563–574) ergänzen:**
```python
def _display_meta(self):
    if not self.video_info:
        return
    # ... bisheriger Code (meta_text.setText) ...

    # NEU: Zusammenfassung setzen und einklappen
    transcript_status = "Transkript ✓" if self.video_info.transcript else "Kein Transkript"
    self.meta_section.set_summary(
        f"✓ {self.video_info.title[:40]}… · {self.video_info.channel} "
        f"· {self.video_info.duration_formatted} · {transcript_status}"
    )
    self.meta_section.collapse()
```

**Vor dem Fetch:** Sektion ausgeklappt (Standard), leere Zusammenfassung.

---

### Schritt 3: Zeitbereich-Sektion umbauen

**Betrifft:** `main_window.py` → `_create_time_range_section()` (Zeile 225–262)

**Aktuell:** `QFrame` mit Checkbox + Start/Ende + Kontext-Checkbox, immer sichtbar im `main_layout`.

**Neu:** Ersetze `QFrame` durch `CollapsibleSection`:
```python
def _create_time_range_section(self) -> CollapsibleSection:
    self.time_range_section = CollapsibleSection("Zeitbereich (optional)")
    self.time_range_section.set_summary("Inaktiv")
    # Body: die bisherigen Controls (Checkbox, Start/Ende, Kontext)
    content = QWidget()
    layout = QVBoxLayout(content)
    # ... bestehender Code für Checkbox, time_start_edit, time_end_edit, time_context_checkbox ...
    self.time_range_section.set_content_widget(content)
    self.time_range_section.collapse()  # Standard: eingeklappt
    return self.time_range_section
```

**Zusammenfassung dynamisch aktualisieren** — bei Änderung der Zeitfelder:
```python
# Neuer Slot, verbinden mit time_start_edit.textChanged und time_end_edit.textChanged
def _update_time_range_summary(self):
    if not self.time_range_checkbox.isChecked():
        self.time_range_section.set_summary("Inaktiv")
        return
    start = self.time_start_edit.text() or "00:00"
    end = self.time_end_edit.text() or "?"
    context = " (mit Kontext)" if self.time_context_checkbox.isChecked() else ""
    self.time_range_section.set_summary(f"{start} – {end}{context}")
```

**Wichtig:** Der `_on_input_tab_changed` (Zeile 510): `self.time_range_frame` → `self.time_range_section`

---

### Schritt 4: Transkript-Brücke (YouTube → Transkript-Tab)

**Betrifft:** `main_window.py` → `_on_get_meta()` (Zeile 545–561) und `TranscriptInputWidget`

**Problem:** `get_video_info()` holt intern ein Transkript (falls verfügbar), aber es wird
nicht im Transkript-Tab angezeigt. Der Nutzer kann es weder sehen noch editieren.

**Lösung — in `_on_get_meta()` nach erfolgreichem Fetch ergänzen:**
```python
@pyqtSlot()
def _on_get_meta(self):
    url = self.url_input.text().strip()
    # ... bisherige Validierung ...
    try:
        self.video_info = get_video_info(url)
        self.video_info_source = "youtube"
        self._display_meta()
        self._clear_stale_sources()
        self.btn_generate.setEnabled(True)

        # NEU: Transkript-Brücke
        if hasattr(self.video_info, 'transcript') and self.video_info.transcript:
            self.transcript_widget.set_auto_transcript(
                transcript=self.video_info.transcript,
                title=self.video_info.title,
                author=self.video_info.channel,
                url=self.video_info.url,
            )
            self._update_transcript_tab_indicator(has_content=True)
    except ValueError as e:
        # ... bisheriger Code ...
```

**In `TranscriptInputWidget` (`src/gui/transcript_widget.py`) eine neue Methode hinzufügen:**
```python
def set_auto_transcript(self, transcript: str, title: str, author: str, url: str = ""):
    """Befüllt das Widget mit einem automatisch geholten Transkript."""
    self._original_transcript = transcript  # Für Zurücksetzen
    self._auto_source = True
    self.title_edit.setText(title)
    self.author_edit.setText(author)
    if url:
        self.url_edit.setText(url)
    self.transcript_edit.setPlainText(transcript)
    self._update_word_count()
    # Hinweistext anzeigen
    self.source_label.setText("✓ Automatisch von YouTube geladen · editierbar")
    self.source_label.setStyleSheet("color: #2E7D32; font-size: 10px;")
    self.reset_btn.setVisible(True)

def reset_transcript(self):
    """Stellt das Original-Transkript wieder her."""
    if hasattr(self, '_original_transcript'):
        self.transcript_edit.setPlainText(self._original_transcript)
        self._update_word_count()
```

**Neue UI-Elemente in `TranscriptInputWidget.__init__`:**
- `self.source_label = QLabel("")` — Hinweistext unter dem Transkript-Feld
- `self.reset_btn = QPushButton("Zurücksetzen")` — nur sichtbar bei auto-fetched, Klick → `reset_transcript()`

---

### Schritt 5: Tab-Umbenennung + Indikator

**Betrifft:** `_setup_ui()` Zeile 153

**Aktuell:**
```python
self.input_tabs.addTab(self.transcript_widget, "Manuelles Transkript")
```

**Neu:**
```python
self.input_tabs.addTab(self.transcript_widget, "Transkript")
```

**Indikator-Methode hinzufügen:**
```python
def _update_transcript_tab_indicator(self, has_content: bool):
    """Zeigt/versteckt den grünen Punkt am Transkript-Tab."""
    tab_index = 1  # Transkript-Tab
    if has_content:
        self.input_tabs.setTabText(tab_index, "Transkript ●")
    else:
        self.input_tabs.setTabText(tab_index, "Transkript")
```

Aufrufen in:
- `_on_get_meta()` nach Transkript-Brücke → `True`
- `transcript_widget.data_changed` Signal → prüfen ob Inhalt vorhanden
- Bei neuer URL / Reset → `False`

---

### Schritt 6: Quellen-Info im Transkript-Tab → CollapsibleSection

**Betrifft:** `TranscriptInputWidget` (`src/gui/transcript_widget.py`)

Falls dort ein QGroupBox "Quellen-Informationen" existiert mit Feldern für Titel, Autor etc.,
dieses ebenfalls durch `CollapsibleSection` ersetzen:
- Bei YouTube-Quelle (auto): Eingeklappt, Zusammenfassung `"✓ YouTube · automatisch"`
- Bei manueller Quelle: Ausgeklappt, Felder leer zum Ausfüllen

**Falls kein QGroupBox existiert:** Schritt überspringen, die Felder (Titel, Autor) bleiben wie sie sind.

---

## ⚠️ Wichtige Hinweise für die Implementierung

1. **Keine Funktionalität entfernen.** Alle bisherigen Features müssen weiterhin funktionieren.
2. **`video_info.transcript`** — Prüfe in `youtube_client.py` bzw. `defaults.py`, ob `VideoInfo`
   ein `transcript`-Feld hat. Falls nicht, muss es ergänzt werden (das Transkript wird ja intern
   schon geholt, es muss nur im VideoInfo-Objekt gespeichert werden).
3. **Prompt-Generierung** darf nicht brechen. Testen mit YouTube-Tab UND Transkript-Tab.
4. **`_on_input_tab_changed`** (Zeile 510): `self.time_range_frame` → `self.time_range_section`
5. **Branch:** `feature/ui-redesign-collapsible` von `main`
6. **Commits:** Einer pro Schritt (6 Commits), damit Rollback pro Feature möglich ist.

---

## 🧪 Testfälle

| # | Test | Erwartung |
|---|------|-----------|
| 1 | App starten (kein Video) | Metadaten-Sektion leer/ausgeklappt, Zeitbereich eingeklappt "Inaktiv" |
| 2 | URL eingeben → Get Meta | Meta lädt → Sektion klappt ein mit Zusammenfassung |
| 3 | Metadaten-Header klicken | Sektion klappt auf → editierbarer QTextEdit sichtbar |
| 4 | Transkript-Tab wechseln | Auto-Transkript da, editierbar, Zähler korrekt, grüner Punkt am Tab |
| 5 | Transkript editieren → Generate | Editierte Version wird im Prompt verwendet |
| 6 | "Zurücksetzen" klicken | Original-Transkript wiederhergestellt |
| 7 | Zeitbereich aktivieren + Zeiten eingeben | Zusammenfassung zeigt z.B. "02:30 – 14:15" |
| 8 | Zeitbereich deaktivieren | Zusammenfassung zeigt "Inaktiv" |
| 9 | Neue URL eingeben → Get Meta | Alles aktualisiert (alte Daten ersetzt, Transkript-Tab neu) |
| 10 | Manuell Transkript einfügen (ohne YouTube) | Tab funktioniert wie bisher, kein "Zurücksetzen"-Button |
| 11 | Generate Prompt (YouTube-Tab) | Prompt korrekt |
| 12 | Generate Prompt (Transkript-Tab, auto-fetched) | Prompt korrekt |
| 13 | Generate Prompt (Transkript-Tab, manuell) | Prompt korrekt |
| 14 | API-Automatik mit Collapsible-Sektionen | Funktioniert wie bisher |
