"""Tests für WordPress-Beitragsbild (featured image), gemockt – kein Netzwerk.

Deckt ab: upload_media baut den Request korrekt, post() nimmt featured_media in
den Payload, publish_post lädt das Thumbnail + reicht die media_id weiter, und
der nicht-fatale Fehlerfall (Download/Upload scheitert) postet trotzdem den Text.

Lauf (ohne pytest):  python tests/test_wordpress_media.py
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core import wordpress_client as wp
from src.core.wordpress_client import (
    WordPressClient, WordPressConfig, WordPressError, publish_post,
)

_CONFIG = WordPressConfig(url="https://example.test", username="user")


def _resp(status=200, json_data=None, content=b"") -> MagicMock:
    """Baut eine Mock-Response mit raise_for_status/json/content."""
    r = MagicMock()
    r.status_code = status
    r.content = content
    r.json.return_value = json_data if json_data is not None else {}
    if status >= 400:
        err = wp.requests.HTTPError(response=r)
        r.raise_for_status.side_effect = err
    else:
        r.raise_for_status.return_value = None
    return r


def test_upload_media_builds_request() -> None:
    """upload_media: korrekter Endpoint, Header, Body = rohe Bytes; gibt id zurück."""
    client = WordPressClient(_CONFIG, "pw")
    with patch.object(wp.requests, "post", return_value=_resp(json_data={"id": 42})) as mock_post:
        media_id = client.upload_media(b"\xff\xd8jpegbytes", "somas-thumbnail-abc.jpg")

    assert media_id == 42
    _, kwargs = mock_post.call_args
    args, _ = mock_post.call_args
    assert args[0].endswith("/wp-json/wp/v2/media"), args[0]
    assert kwargs["data"] == b"\xff\xd8jpegbytes"
    headers = kwargs["headers"]
    assert headers["Content-Disposition"] == 'attachment; filename="somas-thumbnail-abc.jpg"'
    assert headers["Content-Type"] == "image/jpeg"
    assert kwargs["auth"] is client._auth
    print("  upload_media_builds_request: Endpoint/Header/Body/Auth korrekt OK")


def test_upload_media_403_raises() -> None:
    """upload_media: 403 (fehlende upload_files-Rechte) -> WordPressError, kein Crash."""
    client = WordPressClient(_CONFIG, "pw")
    with patch.object(wp.requests, "post", return_value=_resp(status=403, json_data={"message": "keine Rechte"})):
        try:
            client.upload_media(b"x", "f.jpg")
        except WordPressError as exc:
            assert "403" in str(exc)
            print("  upload_media_403_raises: 403 -> WordPressError OK")
            return
    raise AssertionError("WordPressError erwartet")


def test_post_featured_media_in_payload() -> None:
    """post(): featured_media landet im Payload; ohne Angabe fehlt der Schlüssel."""
    client = WordPressClient(_CONFIG, "pw")
    with patch.object(wp.requests, "post", return_value=_resp(json_data={"id": 7, "link": "L"})) as mock_post:
        client.post("T", "<p>x</p>", featured_media=99)
        payload = mock_post.call_args.kwargs["json"]
        assert payload.get("featured_media") == 99, payload

    with patch.object(wp.requests, "post", return_value=_resp(json_data={"id": 7, "link": "L"})) as mock_post:
        client.post("T", "<p>x</p>")
        payload = mock_post.call_args.kwargs["json"]
        assert "featured_media" not in payload, payload
    print("  post_featured_media_in_payload: gesetzt/weggelassen korrekt OK")


def _patch_publish_internals(upload_side_effect=None, upload_return=99):
    """Patcht markdown, Taxonomien, download und upload/post für publish_post."""
    p_md = patch.object(wp, "markdown_to_html", return_value="<p>x</p>")
    p_terms = patch.object(WordPressClient, "resolve_terms", return_value=[])
    upload_mock = MagicMock(side_effect=upload_side_effect, return_value=upload_return)
    p_upload = patch.object(WordPressClient, "upload_media", upload_mock)
    post_mock = MagicMock(return_value=(5, "https://example.test/?p=5"))
    p_post = patch.object(WordPressClient, "post", post_mock)
    return p_md, p_terms, p_upload, p_post, upload_mock, post_mock


def test_publish_post_sets_featured_media() -> None:
    """publish_post: Thumbnail geladen -> upload -> post(featured_media=media_id)."""
    p_md, p_terms, p_upload, p_post, upload_mock, post_mock = _patch_publish_internals()
    with p_md, p_terms, p_upload, p_post, \
            patch.object(wp.requests, "get", return_value=_resp(content=b"IMG")):
        post_id, link, warning = publish_post(
            _CONFIG, "pw", "Titel", "# Analyse\ntext",
            featured_image_urls=["https://img/maxres.jpg"], video_id="abc123",
        )
    assert (post_id, warning) == (5, None)
    upload_mock.assert_called_once()
    assert upload_mock.call_args.args[0] == b"IMG"
    assert "abc123" in upload_mock.call_args.args[1]  # Dateiname enthält video_id
    assert post_mock.call_args.kwargs["featured_media"] == 99
    print("  publish_post_sets_featured_media: media_id am post durchgereicht OK")


def test_publish_post_download_fails_non_fatal() -> None:
    """publish_post: alle Thumbnail-URLs 404 -> Beitrag ohne Bild + Warnung."""
    p_md, p_terms, p_upload, p_post, upload_mock, post_mock = _patch_publish_internals()
    with p_md, p_terms, p_upload, p_post, \
            patch.object(wp.requests, "get", return_value=_resp(status=404)):
        post_id, link, warning = publish_post(
            _CONFIG, "pw", "Titel", "text",
            featured_image_urls=["https://img/maxres.jpg", "https://img/hq.jpg"],
        )
    assert post_id == 5
    assert warning is not None and "übersprungen" in warning
    upload_mock.assert_not_called()
    assert post_mock.call_args.kwargs["featured_media"] is None
    print("  publish_post_download_fails_non_fatal: Text gepostet, Warnung gesetzt OK")


def test_publish_post_upload_fails_non_fatal() -> None:
    """publish_post: Upload wirft WordPressError -> Beitrag trotzdem, Warnung."""
    err = WordPressError("Bild-Upload fehlgeschlagen (HTTP 403): keine Rechte")
    p_md, p_terms, p_upload, p_post, upload_mock, post_mock = _patch_publish_internals(
        upload_side_effect=err
    )
    with p_md, p_terms, p_upload, p_post, \
            patch.object(wp.requests, "get", return_value=_resp(content=b"IMG")):
        post_id, link, warning = publish_post(
            _CONFIG, "pw", "Titel", "text",
            featured_image_urls=["https://img/maxres.jpg"],
        )
    assert post_id == 5
    assert warning is not None and "403" in warning
    assert post_mock.call_args.kwargs["featured_media"] is None
    print("  publish_post_upload_fails_non_fatal: Text gepostet trotz Upload-Fehler OK")


def test_publish_post_no_thumbnail_transcript() -> None:
    """publish_post ohne featured_image_urls (Transkript): kein Download, kein Bild."""
    p_md, p_terms, p_upload, p_post, upload_mock, post_mock = _patch_publish_internals()
    with p_md, p_terms, p_upload, p_post, \
            patch.object(wp.requests, "get") as get_mock:
        post_id, link, warning = publish_post(_CONFIG, "pw", "Titel", "text")
    assert (post_id, warning) == (5, None)
    get_mock.assert_not_called()
    upload_mock.assert_not_called()
    assert post_mock.call_args.kwargs["featured_media"] is None
    print("  publish_post_no_thumbnail_transcript: sauber ohne Bild OK")


def main() -> None:
    """Führt alle WordPress-Beitragsbild-Tests aus."""
    print("WordPress-Beitragsbild-Tests:")
    test_upload_media_builds_request()
    test_upload_media_403_raises()
    test_post_featured_media_in_payload()
    test_publish_post_sets_featured_media()
    test_publish_post_download_fails_non_fatal()
    test_publish_post_upload_fails_non_fatal()
    test_publish_post_no_thumbnail_transcript()
    print("ALLE TESTS OK")


if __name__ == "__main__":
    main()
