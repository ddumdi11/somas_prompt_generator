# API-Integration für SOMAS Prompt Generator

> **Entwicklungsanweisung für Claude Code – Phase 3: API-Automatisierung**
>
> Erstellt von: Claude.ai (Architekt)  
> Für: Claude Code (Implementierung)  
> Supervisor: Thorsten

---

## 🎯 Ziel dieser Phase

Der SOMAS Prompt Generator soll um **automatische LLM-API-Aufrufe** erweitert werden. Der Nutzer kann optional ein Modell auswählen, und der generierte Prompt wird automatisch an die API gesendet. Das Ergebnis erscheint direkt im Analyse-Ergebnis-Feld.

**Wichtig:** Der manuelle Workflow (Copy Prompt → Paste Result) bleibt vollständig erhalten!

---

## 📋 Anforderungen

### Funktionale Anforderungen

1. **API-Modus Toggle**
   - Checkbox oder Toggle: "API-Automatik aktivieren"
   - Wenn aktiv: Nach "Generate Prompt" wird automatisch der API-Call getriggert
   - Wenn inaktiv: Verhalten wie bisher (manueller Copy/Paste-Workflow)

2. **Provider-/Modell-Auswahl**
   - Dropdown für Provider (Perplexity, OpenRouter, ...)
   - Dropdown für Modell (dynamisch basierend auf Provider)
   - Modell-Liste soll **dynamisch von der API abgerufen** werden
   - Zuletzt gewähltes Modell als Default speichern

3. **Status-Anzeige**
   - Visuelle Anzeige des API-Status:
     - 🔵 **Sending** – Request wird gesendet
     - 🟡 **Processing** – Warte auf Antwort
     - 🟢 **Received** – Antwort erfolgreich empfangen
     - 🔴 **Error** – Fehler aufgetreten (mit Fehlermeldung)
   - Position: Neben dem Analyse-Ergebnis-Feld oder als separate Statuszeile

4. **Settings-Dialog**
   - Aufruf über Zahnrad-Symbol (⚙️) neben dem Modell-Dropdown
   - Inhalte:
     - API-Keys verwalten (hinzufügen, ändern, löschen)
     - Provider aktivieren/deaktivieren
     - Default-Modell festlegen
   - API-Keys werden **verschlüsselt** gespeichert (siehe unten)

5. **LinkedIn-Export-Header**
   - Nach API-Nutzung: Modell + Provider im Header anzeigen
   - Format: `SOMAS-Analyse (von [Modell], [Provider])`
   - Beispiel: `SOMAS-Analyse (von Gemini 3 Pro, Perplexity)`

### Nicht-funktionale Anforderungen

- **Non-blocking UI**: API-Calls in separatem Thread (QThread)
- **Sichere Key-Speicherung**: Über `keyring` Bibliothek (OS-native Credential Manager)
- **Portabilität**: Nicht-sensitive Config in JSON-Datei (kopierbar)
- **Graceful Degradation**: App funktioniert auch ohne konfigurierte API

---

## 🏗️ Architektur

### Neue Dateien

```
src/
├── core/
│   ├── api_client.py          # Abstrakte Basis-Klasse für LLM-Clients
│   ├── perplexity_client.py   # Perplexity-Implementation
│   ├── openrouter_client.py   # OpenRouter-Implementation (optional, später)
│   └── api_worker.py          # QThread-Worker für async API-Calls
│
├── config/
│   ├── api_config.py          # API-Konfiguration laden/speichern
│   └── api_providers.json     # Provider-Definitionen (nicht Keys!)
│
└── gui/
    ├── main_window.py         # Erweitern um API-Sektion
    └── settings_dialog.py     # NEU: Settings-Dialog für API-Keys
```

### Datenmodelle

```python
# src/config/api_config.py
from dataclasses import dataclass
from enum import Enum

class APIStatus(Enum):
    IDLE = "idle"
    SENDING = "sending"
    PROCESSING = "processing"
    RECEIVED = "received"
    ERROR = "error"

@dataclass
class APIProvider:
    id: str                    # z.B. "perplexity"
    name: str                  # z.B. "Perplexity AI"
    base_url: str              # z.B. "https://api.perplexity.ai"
    models_endpoint: str       # z.B. "/models" (für dynamische Liste)
    chat_endpoint: str         # z.B. "/chat/completions"
    requires_online: bool      # Perplexity: True (Web-Search)

@dataclass
class APIResponse:
    status: APIStatus
    content: str = ""
    error_message: str = ""
    model_used: str = ""
    provider_used: str = ""
    tokens_used: int = 0
```

---

## 🔐 Sichere Key-Speicherung

### Bibliothek: `keyring`

```python
import keyring

SERVICE_NAME = "somas_prompt_generator"

def save_api_key(provider_id: str, api_key: str) -> None:
    """Speichert API-Key sicher im OS Credential Manager."""
    keyring.set_password(SERVICE_NAME, f"{provider_id}_api_key", api_key)

def get_api_key(provider_id: str) -> str | None:
    """Holt API-Key aus dem OS Credential Manager."""
    return keyring.get_password(SERVICE_NAME, f"{provider_id}_api_key")

def delete_api_key(provider_id: str) -> None:
    """Löscht API-Key aus dem OS Credential Manager."""
    try:
        keyring.delete_password(SERVICE_NAME, f"{provider_id}_api_key")
    except keyring.errors.PasswordDeleteError:
        pass  # Key existierte nicht
```

### Was wird WO gespeichert?

| Daten | Speicherort | Verschlüsselt? |
|-------|-------------|----------------|
| API-Keys | OS Credential Manager (keyring) | ✅ Ja (OS-level) |
| Provider-Definitionen | `api_providers.json` | ❌ Nein (öffentlich) |
| Zuletzt gewähltes Modell | `user_preferences.json` | ❌ Nein |
| Cached Modell-Listen | In-Memory (Session) | – |

---

## 🔄 Threading für Non-Blocking UI

```python
# src/core/api_worker.py
from PyQt6.QtCore import QThread, pyqtSignal
from .api_client import LLMClient, APIResponse, APIStatus

class APIWorker(QThread):
    """Worker-Thread für API-Aufrufe ohne UI-Blockierung."""
    
    status_changed = pyqtSignal(str)      # "sending", "processing", "received", "error"
    response_received = pyqtSignal(object)  # APIResponse-Objekt
    error_occurred = pyqtSignal(str)       # Fehlermeldung
    
    def __init__(self, client: LLMClient, prompt: str, model: str):
        super().__init__()
        self.client = client
        self.prompt = prompt
        self.model = model
    
    def run(self):
        self.status_changed.emit("sending")
        try:
            # Hier könnte man "processing" emittieren wenn die API
            # Streaming unterstützt und der erste Chunk kommt
            self.status_changed.emit("processing")
            
            response = self.client.send_prompt(self.prompt, self.model)
            
            if response.status == APIStatus.RECEIVED:
                self.status_changed.emit("received")
                self.response_received.emit(response)
            else:
                self.status_changed.emit("error")
                self.error_occurred.emit(response.error_message)
                
        except Exception as e:
            self.status_changed.emit("error")
            self.error_occurred.emit(str(e))
```

---

## 🌐 Perplexity API Client

### Endpoint-Dokumentation

- **Base URL:** `https://api.perplexity.ai`
- **Chat Completions:** `POST /chat/completions`
- **Models:** Leider keine `/models` Endpoint – Liste muss hardcoded werden

### Verfügbare Modelle (Stand Januar 2026)

```python
PERPLEXITY_MODELS = [
    # Aktuelle Modellnamen (vereinfacht seit 2025)
    "sonar",           # Balanced - Geschwindigkeit & Kosten
    "sonar-pro",       # Best für komplexe Queries (ehem. huge/large)
    "sonar-reasoning", # Spezialisiert für Reasoning-Tasks
]
```

**Hinweis für Pro-User:** $5 monatliches API-Guthaben inklusive (verfällt am Monatsende).

### Implementation

```python
# src/core/perplexity_client.py
import requests
from .api_client import LLMClient, APIResponse, APIStatus

class PerplexityClient(LLMClient):
    """Perplexity AI API Client."""
    
    BASE_URL = "https://api.perplexity.ai"
    PROVIDER_ID = "perplexity"
    PROVIDER_NAME = "Perplexity AI"
    
    # Aktuelle Modellnamen (Stand Januar 2026)
    MODELS = [
        {"id": "sonar", "name": "Sonar", "description": "Balanced - Geschwindigkeit & Kosten"},
        {"id": "sonar-pro", "name": "Sonar Pro", "description": "Best für komplexe Queries"},
        {"id": "sonar-reasoning", "name": "Sonar Reasoning", "description": "Spezialisiert für Reasoning"},
    ]
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def get_available_models(self) -> list[dict]:
        """Gibt Liste der verfügbaren Modelle zurück."""
        # Perplexity hat keinen /models Endpoint, daher hardcoded
        return self.MODELS
    
    def send_prompt(self, prompt: str, model: str) -> APIResponse:
        """Sendet Prompt an Perplexity API."""
        try:
            response = requests.post(
                f"{self.BASE_URL}/chat/completions",
                headers=self.headers,
                json={
                    "model": model,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ]
                },
                timeout=120  # 2 Minuten Timeout für lange Analysen
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                tokens = data.get("usage", {}).get("total_tokens", 0)
                
                return APIResponse(
                    status=APIStatus.RECEIVED,
                    content=content,
                    model_used=model,
                    provider_used=self.PROVIDER_NAME,
                    tokens_used=tokens
                )
            else:
                return APIResponse(
                    status=APIStatus.ERROR,
                    error_message=f"HTTP {response.status_code}: {response.text}"
                )
                
        except requests.Timeout:
            return APIResponse(
                status=APIStatus.ERROR,
                error_message="Timeout: API antwortet nicht innerhalb von 2 Minuten"
            )
        except Exception as e:
            return APIResponse(
                status=APIStatus.ERROR,
                error_message=str(e)
            )
```

---

## 🖼️ GUI-Erweiterung

### Neues UI-Layout (API-Sektion)

```
┌─────────────────────────────────────────────────────────────────┐
│  ...bestehende Felder (URL, Meta, Fragen, Preset)...            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─ API-MODUS ─────────────────────────────────────────────┐   │
│  │  [✓] API-Automatik aktivieren                           │   │
│  │                                                          │   │
│  │  Provider: [Perplexity AI          ▼]                   │   │
│  │  Modell:   [Sonar Large (Online)   ▼] [⚙️]              │   │
│  │                                                          │   │
│  │  Status:   ⚪ Bereit                                     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  [Generate Prompt]                                              │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  GENERIERTER PROMPT                                    [Copy]   │
│  ...                                                            │
├─────────────────────────────────────────────────────────────────┤
│  ANALYSE-ERGEBNIS                    [Status: 🟢 Received]      │
│  ...                                                            │
└─────────────────────────────────────────────────────────────────┘
```

### Status-Farben

```python
STATUS_COLORS = {
    "idle": ("⚪", "#808080", "Bereit"),
    "sending": ("🔵", "#2196F3", "Sende..."),
    "processing": ("🟡", "#FFC107", "Verarbeite..."),
    "received": ("🟢", "#4CAF50", "Empfangen"),
    "error": ("🔴", "#F44336", "Fehler"),
}
```

---

## 📝 Settings-Dialog

### Wireframe

```
┌─────────────────────────────────────────────────────────────┐
│  ⚙️ API-Einstellungen                                [X]    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  PROVIDER                                                   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  ☑ Perplexity AI                                    │   │
│  │     API-Key: [************************] [👁] [Test] │   │
│  │     Status:  ✅ Verbunden (12 Modelle verfügbar)    │   │
│  │                                                     │   │
│  │  ☐ OpenRouter                                       │   │
│  │     API-Key: [Nicht konfiguriert        ] [👁] [Test]   │
│  │     Status:  ⚠️ Kein API-Key                        │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  DEFAULT-EINSTELLUNGEN                                      │
│  Default-Provider: [Perplexity AI          ▼]              │
│  Default-Modell:   [Sonar Large (Online)   ▼]              │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                    [Speichern]  [Abbrechen]          │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Funktionen

- **API-Key anzeigen/verstecken:** 👁 Button (toggle password visibility)
- **Test-Button:** Validiert den Key durch API-Aufruf (z.B. Models-Liste abrufen)
- **Status-Anzeige:** Zeigt ob Verbindung funktioniert und wie viele Modelle verfügbar

---

## 📦 Neue Dependencies

Ergänzung für `requirements.txt`:

```txt
# API Integration
requests>=2.31.0
keyring>=24.0.0
```

---

## 🚀 Implementierungsreihenfolge

### Schritt 1: Grundgerüst (API-Client)
1. `api_client.py` – Abstrakte Basis-Klasse
2. `perplexity_client.py` – Perplexity-Implementation
3. `api_config.py` – Key-Verwaltung mit keyring
4. Manueller Test via Python-Konsole

### Schritt 2: Threading
1. `api_worker.py` – QThread-Worker
2. Signal/Slot-Verbindungen testen

### Schritt 3: GUI-Integration
1. API-Sektion in `main_window.py` hinzufügen
2. Checkbox, Provider-Dropdown, Modell-Dropdown, Status-Label
3. Zahnrad-Button (führt zunächst zu MessageBox "Coming soon")

### Schritt 4: Settings-Dialog
1. `settings_dialog.py` – Vollständiger Dialog
2. API-Key-Eingabe mit Passwort-Feld
3. Test-Button-Funktionalität
4. Speichern/Laden der Konfiguration

### Schritt 5: LinkedIn-Export-Anpassung
1. `linkedin_formatter.py` erweitern
2. Modell/Provider in Header einfügen wenn API genutzt wurde

### Schritt 6: OpenRouter (parallel zu Perplexity)
1. `openrouter_client.py` – Implementation
2. OpenRouter hat `/models` Endpoint → dynamische Liste möglich
3. Vorteil: 200+ Modelle, oft günstigere Preise, kostenlose Testmodelle

---

## 🌐 OpenRouter API Client

### Endpoint-Dokumentation

- **Base URL:** `https://openrouter.ai/api/v1`
- **Chat Completions:** `POST /chat/completions`
- **Models:** `GET /models` ✅ (dynamische Liste möglich!)

### Besonderheiten

- **200+ Modelle** von verschiedenen Anbietern
- **Kostenlose Testmodelle** bei neuen Releases
- **Dynamische Modell-Liste** via API abrufbar
- **OpenAI-kompatible API** – gleiche Struktur wie Perplexity

### Implementation

```python
# src/core/openrouter_client.py
import requests
from .api_client import LLMClient, APIResponse, APIStatus

class OpenRouterClient(LLMClient):
    """OpenRouter API Client – Multi-Provider Aggregator."""
    
    BASE_URL = "https://openrouter.ai/api/v1"
    PROVIDER_ID = "openrouter"
    PROVIDER_NAME = "OpenRouter"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/your-repo",  # Optional aber empfohlen
            "X-Title": "SOMAS Prompt Generator"              # App-Name für Analytics
        }
    
    def get_available_models(self) -> list[dict]:
        """Holt aktuelle Modell-Liste dynamisch von der API."""
        try:
            response = requests.get(
                f"{self.BASE_URL}/models",
                headers=self.headers,
                timeout=30
            )
            if response.status_code == 200:
                data = response.json()
                # Filter: Nur Chat-fähige Modelle
                return [
                    {
                        "id": m["id"],
                        "name": m.get("name", m["id"]),
                        "description": m.get("description", ""),
                        "context_length": m.get("context_length", 0),
                        "pricing": m.get("pricing", {})
                    }
                    for m in data.get("data", [])
                    if "chat" in m.get("id", "").lower() or True  # Alle Chat-Modelle
                ]
        except Exception:
            pass
        # Fallback auf hardcoded Liste
        return self.FALLBACK_MODELS
    
    def send_prompt(self, prompt: str, model: str) -> APIResponse:
        """Sendet Prompt an OpenRouter API."""
        # Gleiche Struktur wie Perplexity (OpenAI-kompatibel)
        ...
```

---

## ⚠️ Wichtige Hinweise

1. **Timeout beachten:** SOMAS-Analysen können lange dauern (60-120 Sekunden)
2. **Fehlerbehandlung:** Netzwerkfehler, Rate Limits, ungültige Keys abfangen
3. **UI-Feedback:** Nutzer muss jederzeit wissen, was passiert
4. **Graceful Degradation:** Ohne API-Key funktioniert die App weiterhin (manueller Modus)
5. **Keine Secrets im Code:** API-Keys niemals hardcoden oder in Git committen

---

## 🧪 Test-Szenarios

1. **Happy Path:** API-Modus aktiv → Generate Prompt → Automatisch Ergebnis
2. **Manueller Override:** API-Modus aktiv, aber User klickt "Copy" und fügt manuell ein
3. **Kein API-Key:** Settings öffnen, "Bitte API-Key eingeben" Hinweis
4. **Falscher API-Key:** Test-Button zeigt Fehler, speichern trotzdem möglich
5. **Timeout:** Nach 120s Timeout-Fehler anzeigen, UI bleibt responsiv
6. **Wechsel während Request:** Provider wechseln während Request läuft → alten abbrechen?

---

## 📞 Fragen an Thorsten (für Claude Code)

Falls während der Implementierung Unklarheiten auftreten:

1. Soll ein laufender API-Request abgebrochen werden können? (Cancel-Button)
2. Soll die Token-Anzahl/Kosten angezeigt werden?
3. Soll es einen "Retry"-Button bei Fehlern geben?

---

*Erstellt: 2025-01-31 | Version: 1.0*
