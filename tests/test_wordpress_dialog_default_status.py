"""Sicherheits-Vorwahl im WordPress-Sende-Dialog: immer „Privat".

Der Dialog wählt den Beitragsstatus beim Öffnen bewusst auf ``private`` vor —
unabhängig vom in den Settings gespeicherten ``default_status`` — damit ein
Beitrag nie versehentlich sofort veröffentlicht wird (erst auf der Blog-Seite
prüfen, dann manuell freischalten). Der Nutzer kann den Status im Dialog
weiterhin frei umstellen.

Läuft headless über die Qt-Offscreen-Plattform.

Lauf (ohne pytest):
    QT_QPA_PLATFORM=offscreen python tests/test_wordpress_dialog_default_status.py
"""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtWidgets import QApplication

import src.gui.wordpress_dialog as wpd
from src.core.wordpress_client import WordPressConfig
from src.gui.wordpress_dialog import WordPressSendDialog


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _make_dialog(app, monkeypatch, saved_status: str) -> WordPressSendDialog:
    """Dialog mit einem in den Settings gespeicherten ``saved_status``."""
    config = WordPressConfig(
        url="https://example.test",
        username="autor",
        default_status=saved_status,
        default_category="",
    )
    monkeypatch.setattr(wpd, "get_wp_config", lambda: config)
    # Credentials-Check nicht am echten Keyring hängen lassen.
    monkeypatch.setattr(wpd, "has_wp_credentials", lambda: True)
    return WordPressSendDialog("### FRAMING\nAnalyse.", "Titel")


def test_defaults_to_private_despite_publish_setting(app, monkeypatch) -> None:
    """Settings-Default „publish" → Dialog steht trotzdem auf „private"."""
    dlg = _make_dialog(app, monkeypatch, saved_status="publish")
    assert dlg.status_combo.currentData() == "private"
    dlg.deleteLater()


def test_defaults_to_private_despite_draft_setting(app, monkeypatch) -> None:
    """Auch ein anderer Settings-Wert („draft") ändert die Vorwahl nicht."""
    dlg = _make_dialog(app, monkeypatch, saved_status="draft")
    assert dlg.status_combo.currentData() == "private"
    dlg.deleteLater()


def test_publish_remains_manually_selectable(app, monkeypatch) -> None:
    """Die Vorwahl ist sicher, aber „publish" bleibt manuell wählbar."""
    dlg = _make_dialog(app, monkeypatch, saved_status="publish")
    assert dlg.status_combo.findData("publish") >= 0
    dlg.deleteLater()


def main() -> None:
    """Minimaler manueller Lauf ohne pytest-Fixtures."""
    print("WordPress-Sende-Dialog Default-Status:")
    QApplication.instance() or QApplication([])

    config = WordPressConfig(url="https://example.test", username="autor",
                             default_status="publish", default_category="")
    wpd.get_wp_config = lambda: config
    wpd.has_wp_credentials = lambda: True
    dlg = WordPressSendDialog("### FRAMING\nAnalyse.", "Titel")
    assert dlg.status_combo.currentData() == "private"
    assert dlg.status_combo.findData("publish") >= 0
    print("  defaults_to_private + publish selectable OK")
    print("ALLE TESTS OK")


if __name__ == "__main__":
    main()
