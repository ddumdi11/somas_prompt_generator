"""Tests für den Intake-Core-Adapter und den Router (vollständig offline).

Der echte `youtube_intake_core` wird NICHT benötigt: er wird als Fake in
`sys.modules` injiziert bzw. gezielt „unavailable" gemacht. So laufen die Tests
unabhängig davon, ob das Submodul/der Core bereits installiert ist.

Lauf: python -m pytest tests/test_intake_adapter.py -q
"""

import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config.defaults import VideoInfo


def _wire_dict(**overrides) -> dict:
    """Baut ein 12-Feld-Erfolgs-dict gemäß eingefrorener Wire-Form (v1.0.0)."""
    d = dict(
        status="complete",
        transcript_available=True,
        title="Titel",
        channel="Kanal",
        duration=125,
        duration_formatted="2:05",
        url="https://youtu.be/abcdefghijk",
        thumbnail_url_maxres="https://i.ytimg.com/vi/abcdefghijk/maxresdefault.jpg",
        transcript="hallo welt",
        markdown="# md",
        warnings=[],
        errors=[],
    )
    d.update(overrides)
    return d


def _install_fake_core(monkeypatch, process_impl):
    """Injiziert ein Fake-`youtube_intake_core`-Modul mit `process` + `IntakeError`."""
    mod = types.ModuleType("youtube_intake_core")

    class IntakeError(Exception):
        def __init__(self, error_code="processing_failed", message="boom"):
            super().__init__(message)
            self.error_code = error_code
            self.message = message

    mod.IntakeError = IntakeError
    mod.process = process_impl
    monkeypatch.setitem(sys.modules, "youtube_intake_core", mod)
    return mod


# --- Adapter: fetch() ---------------------------------------------------------

def test_fetch_complete_maps_to_videoinfo(monkeypatch):
    from src.core import intake_adapter
    _install_fake_core(monkeypatch, lambda url, language="de": _wire_dict())

    res = intake_adapter.fetch("https://youtu.be/abcdefghijk")

    assert isinstance(res.video_info, VideoInfo)
    assert res.video_info.title == "Titel"
    assert res.video_info.channel == "Kanal"
    assert res.video_info.duration == 125
    assert res.video_info.transcript == "hallo welt"
    assert res.status == "complete"
    assert res.transcript_available is True


def test_fetch_metadata_only(monkeypatch):
    from src.core import intake_adapter
    _install_fake_core(
        monkeypatch,
        lambda url, language="de": _wire_dict(
            status="metadata_only",
            transcript_available=False,
            transcript="",
            warnings=["Transkript-Sprache: en (Fallback von de)"],
        ),
    )

    res = intake_adapter.fetch("u")

    assert res.status == "metadata_only"
    assert res.transcript_available is False
    assert res.video_info.transcript == ""
    assert res.warnings == ["Transkript-Sprache: en (Fallback von de)"]


def test_fetch_hard_error_becomes_intakefailed(monkeypatch):
    from src.core import intake_adapter
    mod = _install_fake_core(monkeypatch, None)

    def boom(url, language="de"):
        raise mod.IntakeError("invalid_url", "keine gültige URL")

    mod.process = boom

    with pytest.raises(intake_adapter.IntakeFailed) as excinfo:
        intake_adapter.fetch("u")
    assert excinfo.value.error_code == "invalid_url"
    assert "gültige URL" in excinfo.value.message


def test_fetch_missing_core_is_unavailable(monkeypatch):
    from src.core import intake_adapter
    # None in sys.modules erzwingt ImportError beim Import — robust, egal ob der
    # echte Core installiert ist oder nicht.
    monkeypatch.setitem(sys.modules, "youtube_intake_core", None)

    with pytest.raises(intake_adapter.IntakeUnavailable):
        intake_adapter.fetch("u")


def test_fetch_broken_wireform_is_intakefailed(monkeypatch):
    from src.core import intake_adapter
    _install_fake_core(monkeypatch, lambda url, language="de": {"title": "nur titel"})

    with pytest.raises(intake_adapter.IntakeFailed) as excinfo:
        intake_adapter.fetch("u")
    assert excinfo.value.error_code == "mapping_error"


def test_fetch_generic_error_becomes_intakefailed(monkeypatch):
    from src.core import intake_adapter
    mod = _install_fake_core(monkeypatch, None)

    def boom(url, language="de"):
        raise RuntimeError("irgendwas Unerwartetes im Core")

    mod.process = boom

    # Nicht-IntakeError darf NICHT roh entkommen (sonst bricht der ValueError-
    # Kontrakt der Aufrufer) → als IntakeFailed mit generischem Code.
    with pytest.raises(intake_adapter.IntakeFailed) as excinfo:
        intake_adapter.fetch("u")
    assert excinfo.value.error_code == "processing_failed"


def test_fetch_nonlist_warnings_is_intakefailed(monkeypatch):
    from src.core import intake_adapter
    _install_fake_core(
        monkeypatch,
        lambda url, language="de": _wire_dict(warnings="kein array"),
    )

    # Nicht-Listen-warnings werden NICHT still coerct, sondern fail-fast.
    with pytest.raises(intake_adapter.IntakeFailed) as excinfo:
        intake_adapter.fetch("u")
    assert excinfo.value.error_code == "mapping_error"


# --- Router: resolve_video_info() --------------------------------------------

def test_resolve_use_core_false_uses_old_path(monkeypatch):
    from src.core import youtube_client
    calls = {}

    def fake_old(url):
        calls["url"] = url
        return "OLD"

    monkeypatch.setattr(youtube_client, "get_video_info", fake_old)

    assert youtube_client.resolve_video_info("u", use_core=False) == "OLD"
    assert calls["url"] == "u"


def test_resolve_use_core_true_success(monkeypatch):
    from src.core import youtube_client, intake_adapter
    vi = VideoInfo(title="T", channel="C", duration=1, url="u", transcript="")
    monkeypatch.setattr(
        intake_adapter, "fetch",
        lambda url, language="de": intake_adapter.IntakeResult(vi, "complete", False, ["w"]),
    )
    monkeypatch.setattr(
        youtube_client, "get_video_info",
        lambda url: pytest.fail("Alt-Pfad darf bei Core-Erfolg nicht laufen"),
    )

    assert youtube_client.resolve_video_info("u", use_core=True) is vi


def test_resolve_falls_back_on_unavailable(monkeypatch):
    from src.core import youtube_client, intake_adapter

    def boom(url, language="de"):
        raise intake_adapter.IntakeUnavailable("kein Core")

    monkeypatch.setattr(intake_adapter, "fetch", boom)
    monkeypatch.setattr(youtube_client, "get_video_info", lambda url: "OLD")

    assert youtube_client.resolve_video_info("u", use_core=True) == "OLD"


def test_resolve_hard_error_raises_valueerror(monkeypatch):
    from src.core import youtube_client, intake_adapter

    def boom(url, language="de"):
        raise intake_adapter.IntakeFailed("video_unavailable", "Video weg")

    monkeypatch.setattr(intake_adapter, "fetch", boom)
    monkeypatch.setattr(
        youtube_client, "get_video_info",
        lambda url: pytest.fail("Bei hartem Fehler KEIN Fallback erwartet"),
    )

    with pytest.raises(ValueError):
        youtube_client.resolve_video_info("u", use_core=True)
