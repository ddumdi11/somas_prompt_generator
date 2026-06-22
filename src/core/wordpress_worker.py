"""Wiederverwendbarer QThread-Worker für blockierende WordPress-Operationen.

Sowohl der Verbindungstest (Einstellungen) als auch das Senden eines Beitrags
(Sende-Dialog) sind Netzwerk-Operationen, die den GUI-Thread einfrieren würden.
Dieser Worker führt eine beliebige Funktion im Hintergrund aus und meldet das
Ergebnis bzw. einen Fehler per Signal zurück.

Wichtig (PyQt-Konventionen):
- Im ``run()`` werden **keine** Widgets angefasst – ausschließlich Signals
  emittiert. Das UI-Update erfolgt in den verbundenen Slots im Main-Thread.
- Der Aufrufer muss eine Referenz auf die Worker-Instanz halten, sonst wird der
  QThread vorzeitig vom Garbage Collector eingesammelt.
"""

import logging
from typing import Any, Callable

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)


class WordPressWorker(QThread):
    """Führt eine blockierende Funktion im Hintergrund aus.

    Signals:
        succeeded: Emittiert das Rückgabeobjekt der Funktion bei Erfolg.
        failed: Emittiert eine Fehlermeldung (str) bei einer Exception.
    """

    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        """Initialisiert den Worker.

        Args:
            fn: Die im Hintergrund auszuführende (blockierende) Funktion.
            *args: Positionsargumente für ``fn``.
            **kwargs: Schlüsselwortargumente für ``fn``.
        """
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self) -> None:
        """Führt die Funktion aus und meldet Ergebnis oder Fehler per Signal."""
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as exc:  # noqa: BLE001 – bewusst alles abfangen, Thread darf nicht crashen
            logger.error("WordPress-Worker fehlgeschlagen: %s", exc)
            self.failed.emit(str(exc))
        else:
            self.succeeded.emit(result)
