#!/usr/bin/env python3
"""SOMAS Prompt Generator - Entry Point.

Desktop-App zur Generierung von SOMAS-Analyse-Prompts für YouTube-Videos.
"""

import sys
import logging

from PyQt6.QtWidgets import QApplication

from src.gui.main_window import MainWindow


def setup_logging():
    """Konfiguriert das Logging für die Anwendung."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ]
    )


def main():
    """Startet die SOMAS Prompt Generator Anwendung."""
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Starte SOMAS Prompt Generator...")

    app = QApplication(sys.argv)
    app.setApplicationName("SOMAS Prompt Generator")

    window = MainWindow()
    window.show()

    logger.info("Anwendung gestartet.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
