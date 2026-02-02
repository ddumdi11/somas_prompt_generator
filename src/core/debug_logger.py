"""Debug-Logger für API-Request/Response-Nachvollziehbarkeit.

Speichert vollständige API-Interaktionen als JSON-Dateien in %TEMP%/somas_debug/
für Fehleranalyse bei Halluzinationen, Fehlidentifikationen und unerwarteten Outputs.
"""

import json
import logging
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

APP_VERSION = "0.3.1"


class DebugLogger:
    """Logs API requests/responses to %TEMP%/somas_debug/.

    Jeder API-Call bekommt ein eigenes Unterverzeichnis mit:
    - request.json (Prompt, Provider, Modell)
    - response.json (Content, Tokens, Dauer, Fehler)
    - meta.json (App-Version, Preset, Video-Infos)

    Aktivierung über User-Preferences (debug_logging: true).
    """

    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled
        self.base_dir = Path(os.environ.get('TEMP', '/tmp')) / 'somas_debug'

    def log_request(
        self,
        provider: str,
        model: str,
        endpoint: str,
        prompt: str,
        meta: dict,
    ) -> Path | None:
        """Logs outgoing API request. Returns log directory path.

        Args:
            provider: Provider-ID (z.B. 'perplexity').
            model: Modell-ID (z.B. 'sonar-pro').
            endpoint: API-Endpoint-URL.
            prompt: Der gesendete Prompt-Text.
            meta: Dict mit App-Version, Preset, Video-Infos etc.

        Returns:
            Pfad zum Log-Verzeichnis oder None wenn deaktiviert.
        """
        if not self.enabled:
            return None

        now = datetime.now()
        timestamp = now.strftime('%Y-%m-%d_%H-%M-%S')
        safe_model = re.sub(r'[<>:"/\\|?*]', '_', model)
        log_dir = self.base_dir / f"{timestamp}_{provider}_{safe_model}"
        log_dir.mkdir(parents=True, exist_ok=True)

        request_data = {
            "timestamp": now.isoformat(),
            "provider": provider,
            "model": model,
            "endpoint": endpoint,
            "prompt_length_chars": len(prompt),
            "prompt": prompt,
        }

        (log_dir / "request.json").write_text(
            json.dumps(request_data, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
        (log_dir / "meta.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )

        logger.info(f"Debug-Log: Request gespeichert in {log_dir}")
        return log_dir

    def log_response(
        self,
        log_dir: Path,
        status_code: int,
        content: str,
        tokens: dict,
        duration: float,
        model_used: str = "",
        citations: list[str] | None = None,
        error: str | None = None,
    ) -> None:
        """Logs received API response.

        Args:
            log_dir: Pfad zum Log-Verzeichnis (von log_request).
            status_code: HTTP-Status-Code.
            content: Antwort-Inhalt.
            tokens: Dict mit 'input', 'output', 'total' Token-Counts.
            duration: Dauer des API-Calls in Sekunden.
            model_used: Tatsächlich verwendetes Modell (kann vom Request abweichen).
            citations: Optionale Quellen-URLs (z.B. von Perplexity).
            error: Fehlermeldung bei API-Fehlern.
        """
        if not self.enabled or log_dir is None:
            return

        response_data = {
            "timestamp_received": datetime.now().isoformat(),
            "duration_seconds": round(duration, 1),
            "status_code": status_code,
            "model_used": model_used,
            "tokens_input": tokens.get("input", 0),
            "tokens_output": tokens.get("output", 0),
            "tokens_total": tokens.get("total", 0),
            "content_length_chars": len(content),
            "error": error is not None,
        }

        if error:
            response_data["error_type"] = "api_error"
            response_data["error_message"] = error

        if citations:
            response_data["citations"] = citations

        response_data["content"] = content

        (log_dir / "response.json").write_text(
            json.dumps(response_data, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )

        logger.info(
            f"Debug-Log: Response gespeichert "
            f"({len(content)} Zeichen, {round(duration, 1)}s)"
        )

    def get_log_count(self) -> int:
        """Gibt die Anzahl vorhandener Debug-Logs zurück."""
        if not self.base_dir.exists():
            return 0
        return sum(1 for d in self.base_dir.iterdir() if d.is_dir())

    def clear_logs(self) -> int:
        """Löscht alle Debug-Logs.

        Returns:
            Anzahl gelöschter Log-Verzeichnisse.
        """
        if not self.base_dir.exists():
            return 0

        count = 0
        for d in self.base_dir.iterdir():
            if d.is_dir():
                try:
                    shutil.rmtree(d)
                    count += 1
                except OSError as e:
                    logger.warning(
                        f"Log-Verzeichnis konnte nicht gelöscht werden: {d} - {e}"
                    )

        logger.info(f"Debug-Logs gelöscht: {count} Einträge")
        return count
