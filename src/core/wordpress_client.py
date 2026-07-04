"""WordPress-Integration: Sendet SOMAS-Analysen als Beitrag an die selbstgehostete
WordPress-Seite via REST-API (`/wp-json/wp/v2/posts`).

Da SOMAS eine Desktop-App ist, entfällt CORS – ein direkter HTTPS-Request mit
HTTP Basic Auth (Benutzername + Application Password) genügt.

Credentials:
- URL, Benutzername, Default-Status, Default-Kategorie -> user_preferences.json
  (nicht sensibel)
- Application Password -> OS Credential Manager (keyring), analog zu den API-Keys.

Markdown -> HTML wird clientseitig konvertiert, da WordPress Beiträge als HTML
speichert.
"""

import logging
from dataclasses import dataclass
from typing import Optional

import keyring
import requests
from requests.auth import HTTPBasicAuth

from src.config.api_config import (
    SERVICE_NAME,
    load_preferences,
    save_preferences,
)

logger = logging.getLogger(__name__)

# Keyring-Schlüssel für das Application Password (analog zu "<provider>_api_key").
_WP_PASSWORD_KEY = "wordpress_app_password"

# Preferences-Schlüssel (nicht-sensible Config).
_PREF_URL = "wordpress_url"
_PREF_USER = "wordpress_user"
_PREF_STATUS = "wordpress_default_status"
_PREF_CATEGORY = "wordpress_default_category"

#: Erlaubte Beitragsstatus laut WordPress-REST-API.
WP_STATUSES = ("draft", "private", "publish", "pending")

#: Standard-Status, wenn nichts konfiguriert ist (sicherste Variante: Entwurf).
DEFAULT_STATUS = "draft"

_REQUEST_TIMEOUT = 30


# --------------------------------------------------------------------------- #
# Datenmodell + Credential-Verwaltung
# --------------------------------------------------------------------------- #


@dataclass
class WordPressConfig:
    """Konfiguration für die WordPress-Verbindung.

    Attributes:
        url: Basis-URL der WordPress-Seite (ohne abschließenden Slash),
            z.B. ``https://diggi.torja.de``.
        username: WordPress-Benutzername mit Veröffentlichungsrecht.
        default_status: Vorausgewählter Beitragsstatus im Sende-Dialog.
        default_category: Optionale Default-Kategorie (Name), die beim Senden
            automatisch angelegt/zugewiesen wird.
    """

    url: str = ""
    username: str = ""
    default_status: str = DEFAULT_STATUS
    default_category: str = ""

    @property
    def is_complete(self) -> bool:
        """True, wenn URL und Benutzername gesetzt sind (Passwort separat)."""
        return bool(self.url.strip() and self.username.strip())


def get_wp_config() -> WordPressConfig:
    """Lädt die WordPress-Konfiguration aus den User-Preferences.

    Returns:
        Befülltes :class:`WordPressConfig` (leer, wenn nichts konfiguriert).
    """
    prefs = load_preferences()
    status = prefs.get(_PREF_STATUS, DEFAULT_STATUS)
    if status not in WP_STATUSES:
        status = DEFAULT_STATUS
    return WordPressConfig(
        url=prefs.get(_PREF_URL, "").rstrip("/"),
        username=prefs.get(_PREF_USER, ""),
        default_status=status,
        default_category=prefs.get(_PREF_CATEGORY, ""),
    )


def save_wp_config(
    url: str,
    username: str,
    default_status: str = DEFAULT_STATUS,
    default_category: str = "",
) -> None:
    """Speichert die nicht-sensible WordPress-Config in den User-Preferences.

    Args:
        url: Basis-URL der WordPress-Seite.
        username: WordPress-Benutzername.
        default_status: Default-Beitragsstatus.
        default_category: Optionale Default-Kategorie.
    """
    prefs = load_preferences()
    prefs[_PREF_URL] = url.strip().rstrip("/")
    prefs[_PREF_USER] = username.strip()
    prefs[_PREF_STATUS] = (
        default_status if default_status in WP_STATUSES else DEFAULT_STATUS
    )
    prefs[_PREF_CATEGORY] = default_category.strip()
    save_preferences(prefs)
    logger.info("WordPress-Konfiguration gespeichert")


def get_wp_app_password() -> Optional[str]:
    """Holt das Application Password aus dem OS Credential Manager.

    Returns:
        Das Passwort oder ``None``, wenn keines hinterlegt ist.
    """
    return keyring.get_password(SERVICE_NAME, _WP_PASSWORD_KEY)


def save_wp_app_password(app_password: str) -> None:
    """Speichert das Application Password sicher im Credential Manager.

    Leerzeichen im WordPress-Passwort werden beibehalten – WordPress akzeptiert
    es mit oder ohne, das Entfernen ist nicht nötig.

    Args:
        app_password: Das von WordPress generierte Application Password.
    """
    keyring.set_password(SERVICE_NAME, _WP_PASSWORD_KEY, app_password)
    logger.info("WordPress Application Password gespeichert")


def delete_wp_app_password() -> None:
    """Löscht das Application Password aus dem Credential Manager."""
    try:
        keyring.delete_password(SERVICE_NAME, _WP_PASSWORD_KEY)
        logger.info("WordPress Application Password gelöscht")
    except keyring.errors.PasswordDeleteError:
        pass  # Passwort existierte nicht


def has_wp_credentials() -> bool:
    """Prüft, ob URL, Benutzername und Application Password vollständig sind.

    Returns:
        True, wenn alle drei Bestandteile vorhanden sind.
    """
    config = get_wp_config()
    return config.is_complete and bool(get_wp_app_password())


# --------------------------------------------------------------------------- #
# Markdown -> HTML + Inhalts-Helfer
# --------------------------------------------------------------------------- #


def markdown_to_html(md_text: str) -> str:
    """Konvertiert Markdown nach HTML für den WordPress-Block-Editor.

    WordPress speichert Beiträge als HTML; roher Markdown würde wörtlich im Post
    landen. Emojis und Unicode bleiben dabei unverändert erhalten.

    Args:
        md_text: Markdown-Quelltext.

    Returns:
        Gerendertes HTML.

    Raises:
        RuntimeError: Wenn das ``markdown``-Paket nicht installiert ist.
    """
    try:
        import markdown
    except ImportError as exc:  # pragma: no cover - reine Abhängigkeitsprüfung
        raise RuntimeError(
            "Das Paket 'markdown' wird benötigt. "
            "Installiere es mit: pip install markdown"
        ) from exc

    return markdown.markdown(
        md_text,
        extensions=["extra", "fenced_code", "tables", "sane_lists"],
    )


def assemble_content(intro_md: str, analysis_md: str, outro_md: str) -> str:
    """Fügt Intro, Analyse und Outro zu einem Markdown-Block zusammen.

    Leere Felder werden ausgelassen, sodass bei leerem Intro/Outro nur die
    Analyse gesendet wird (Variante A: getrennte Felder).

    Args:
        intro_md: Optionaler Einleitungstext (Markdown).
        analysis_md: Die SOMAS-Analyse (Markdown).
        outro_md: Optionaler Ausleitungstext (Markdown).

    Returns:
        Zusammengesetzter Markdown-String (Teile durch Leerzeile getrennt).
    """
    parts = [
        part.strip()
        for part in (intro_md, analysis_md, outro_md)
        if part and part.strip()
    ]
    return "\n\n".join(parts)


def split_title_and_body(md_text: str, fallback_title: str = "Analyse") -> tuple[str, str]:
    """Zieht eine führende H1-Überschrift als Titel heraus, falls vorhanden.

    Vermeidet eine Dopplung, wenn die Analyse mit ``# Titel`` beginnt.

    Args:
        md_text: Markdown-Quelltext.
        fallback_title: Titel, falls keine H1 am Anfang steht.

    Returns:
        Tupel ``(title, body)``.
    """
    lines = md_text.lstrip().splitlines()
    if lines and lines[0].startswith("# "):
        title = lines[0][2:].strip()
        body = "\n".join(lines[1:]).lstrip()
        return title, body
    return fallback_title, md_text


# --------------------------------------------------------------------------- #
# REST-Client
# --------------------------------------------------------------------------- #


class WordPressError(Exception):
    """Fehler bei der Kommunikation mit der WordPress-REST-API."""


class WordPressClient:
    """Schlanker Client für die WordPress-REST-API (Beiträge + Taxonomien).

    Authentifizierung via HTTP Basic Auth mit Benutzername + Application
    Password.
    """

    def __init__(self, config: WordPressConfig, app_password: str) -> None:
        """Initialisiert den Client.

        Args:
            config: WordPress-Konfiguration (URL, Benutzer, Defaults).
            app_password: Das Application Password.
        """
        self.url = config.url.rstrip("/")
        self.username = config.username
        self._auth = HTTPBasicAuth(config.username, app_password)

    # -- intern -------------------------------------------------------------- #

    def _endpoint(self, path: str) -> str:
        return f"{self.url}/wp-json/wp/v2/{path.lstrip('/')}"

    # -- öffentlich ---------------------------------------------------------- #

    def test_connection(self) -> tuple[bool, str]:
        """Testet die Verbindung und die Anmeldedaten.

        Ruft den ``/users/me``-Endpunkt auf, der gültige Credentials verlangt.

        Returns:
            Tupel ``(success, message)`` mit einer benutzerfreundlichen Meldung.
        """
        try:
            resp = requests.get(
                self._endpoint("users/me"),
                auth=self._auth,
                timeout=_REQUEST_TIMEOUT,
            )
        except requests.RequestException as exc:
            return False, f"Verbindung fehlgeschlagen: {exc}"

        if resp.status_code == 200:
            try:
                name = resp.json().get("name", self.username)
            except ValueError:
                name = self.username
            return True, f"Verbunden als '{name}'."
        if resp.status_code in (401, 403):
            return False, "Anmeldung fehlgeschlagen – Benutzer/Passwort prüfen."
        return False, f"Unerwartete Antwort (HTTP {resp.status_code})."

    def get_or_create_term(self, name: str, taxonomy: str = "tags") -> int:
        """Schlägt eine Kategorie/einen Tag nach und legt sie bei Bedarf an.

        Die REST-API erwartet numerische IDs, keine Namen.

        Args:
            name: Anzeigename der Kategorie/des Tags.
            taxonomy: ``"tags"`` oder ``"categories"``.

        Returns:
            Die numerische Term-ID.

        Raises:
            WordPressError: Bei API-Fehlern.
        """
        base = self._endpoint(taxonomy)
        try:
            # 1. Suchen
            resp = requests.get(
                base, params={"search": name}, auth=self._auth,
                timeout=_REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            for term in resp.json():
                if term.get("name", "").lower() == name.lower():
                    return int(term["id"])

            # 2. Nicht gefunden -> anlegen
            resp = requests.post(
                base, json={"name": name}, auth=self._auth,
                timeout=_REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            return int(resp.json()["id"])
        except requests.RequestException as exc:
            raise WordPressError(
                f"Taxonomie '{taxonomy}' konnte nicht verarbeitet werden: {exc}"
            ) from exc
        except (KeyError, ValueError) as exc:
            raise WordPressError(
                f"Unerwartete Antwort beim Anlegen von '{name}': {exc}"
            ) from exc

    def resolve_terms(self, names: list[str], taxonomy: str = "tags") -> list[int]:
        """Wandelt eine Liste von Namen in Term-IDs um (leere werden ignoriert).

        Args:
            names: Namen der Kategorien/Tags.
            taxonomy: ``"tags"`` oder ``"categories"``.

        Returns:
            Liste numerischer IDs.
        """
        ids: list[int] = []
        for name in names:
            cleaned = name.strip()
            if cleaned:
                ids.append(self.get_or_create_term(cleaned, taxonomy))
        return ids

    def upload_media(
        self, image_bytes: bytes, filename: str, mime: str = "image/jpeg",
    ) -> int:
        """Lädt ein Bild in die WordPress-Mediathek hoch.

        Erwartet die rohen Bild-Bytes und lädt sie via ``POST /media`` hoch. Der
        Dateiname wird über den ``Content-Disposition``-Header übermittelt (so
        verlangt es die REST-API für Datei-Uploads).

        Args:
            image_bytes: Die rohen Bilddaten.
            filename: Dateiname für die Mediathek (z.B. ``somas-thumbnail-<id>.jpg``).
            mime: MIME-Typ der Bilddaten (Standard ``image/jpeg``).

        Returns:
            Die numerische Media-ID des angelegten Anhangs.

        Raises:
            WordPressError: Bei API-/Netzwerkfehlern (inkl. 401/403 = fehlende
                ``upload_files``-Rechte).
        """
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": mime,
        }
        try:
            resp = requests.post(
                self._endpoint("media"),
                data=image_bytes,
                headers=headers,
                auth=self._auth,
                timeout=_REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            return int(resp.json()["id"])
        except requests.HTTPError as exc:
            detail = ""
            try:
                detail = exc.response.json().get("message", "")
            except (ValueError, AttributeError):
                detail = exc.response.text[:200] if exc.response is not None else ""
            raise WordPressError(
                f"Bild-Upload fehlgeschlagen (HTTP "
                f"{exc.response.status_code if exc.response is not None else '?'})"
                f"{': ' + detail if detail else ''}"
            ) from exc
        except requests.RequestException as exc:
            raise WordPressError(f"Netzwerkfehler beim Bild-Upload: {exc}") from exc
        except (KeyError, ValueError) as exc:
            raise WordPressError(
                f"Unerwartete Antwort beim Bild-Upload: {exc}"
            ) from exc

    def post(
        self,
        title: str,
        html_content: str,
        status: str = DEFAULT_STATUS,
        category_ids: Optional[list[int]] = None,
        tag_ids: Optional[list[int]] = None,
        featured_media: Optional[int] = None,
    ) -> tuple[int, str]:
        """Erstellt einen Beitrag in WordPress.

        Args:
            title: Beitragstitel.
            html_content: Bereits nach HTML konvertierter Inhalt.
            status: Beitragsstatus (``draft`` | ``publish`` | ``private`` |
                ``pending``).
            category_ids: Optionale Kategorie-IDs.
            tag_ids: Optionale Tag-IDs.
            featured_media: Optionale Media-ID für das Beitragsbild (featured image).

        Returns:
            Tupel ``(post_id, link)``.

        Raises:
            WordPressError: Bei API-/Netzwerkfehlern.
        """
        if status not in WP_STATUSES:
            status = DEFAULT_STATUS

        payload: dict = {
            "title": title,
            "content": html_content,
            "status": status,
        }
        if category_ids:
            payload["categories"] = category_ids
        if tag_ids:
            payload["tags"] = tag_ids
        if featured_media:
            payload["featured_media"] = featured_media

        try:
            resp = requests.post(
                self._endpoint("posts"),
                json=payload,
                auth=self._auth,
                timeout=_REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            return int(data["id"]), data.get("link", "")
        except requests.HTTPError as exc:
            detail = ""
            try:
                detail = exc.response.json().get("message", "")
            except (ValueError, AttributeError):
                detail = exc.response.text[:200] if exc.response is not None else ""
            raise WordPressError(
                f"Beitrag konnte nicht gesendet werden (HTTP "
                f"{exc.response.status_code if exc.response is not None else '?'})"
                f"{': ' + detail if detail else ''}"
            ) from exc
        except requests.RequestException as exc:
            raise WordPressError(f"Netzwerkfehler beim Senden: {exc}") from exc
        except (KeyError, ValueError) as exc:
            raise WordPressError(
                f"Unerwartete Antwort von WordPress: {exc}"
            ) from exc


# --------------------------------------------------------------------------- #
# High-Level-Operationen (für den asynchronen Worker, blockierend ausgeführt)
# --------------------------------------------------------------------------- #


def run_connection_test(config: WordPressConfig, app_password: str) -> tuple[bool, str]:
    """Führt einen Verbindungstest aus (blockierend – im Worker-Thread nutzen).

    Args:
        config: WordPress-Konfiguration.
        app_password: Application Password.

    Returns:
        Tupel ``(success, message)``.
    """
    return WordPressClient(config, app_password).test_connection()


def _download_thumbnail(urls: list[str]) -> Optional[bytes]:
    """Lädt das erste erreichbare Bild aus einer Fallback-Kette von URLs.

    YouTube liefert nicht für jedes Video ein ``maxresdefault.jpg`` (404); daher
    wird die Liste (typisch maxres → hq → sd) der Reihe nach durchprobiert.

    Args:
        urls: Bild-URLs in Prioritätsreihenfolge.

    Returns:
        Die rohen Bild-Bytes oder ``None``, wenn keine URL erreichbar war.
    """
    for url in urls:
        if not url:
            continue
        try:
            resp = requests.get(url, timeout=_REQUEST_TIMEOUT)
            if resp.status_code == 200 and resp.content:
                return resp.content
            logger.info(
                "Thumbnail-URL nicht verfügbar (HTTP %s): %s",
                resp.status_code, url,
            )
        except requests.RequestException as exc:
            logger.info("Thumbnail-URL fehlgeschlagen (%s): %s", exc, url)
    return None


def publish_post(
    config: WordPressConfig,
    app_password: str,
    title: str,
    markdown_content: str,
    status: str = DEFAULT_STATUS,
    category_names: Optional[list[str]] = None,
    tag_names: Optional[list[str]] = None,
    featured_image_urls: Optional[list[str]] = None,
    video_id: str = "",
) -> tuple[int, str, Optional[str]]:
    """Konvertiert Markdown, löst Taxonomien auf und postet (blockierend).

    Diese Funktion bündelt alle Netzwerk-Operationen, damit sie als Einheit im
    Worker-Thread laufen kann.

    Ist ``featured_image_urls`` gesetzt, wird das erste erreichbare Bild geladen,
    in die Mediathek hochgeladen und als Beitragsbild (featured image) gesetzt.
    Das ist **nicht fatal**: Schlägt Laden oder Upload fehl, wird der Beitrag
    trotzdem (ohne Beitragsbild) gepostet und eine Warnung zurückgegeben — der
    Text ist wichtiger als das Bild.

    Args:
        config: WordPress-Konfiguration.
        app_password: Application Password.
        title: Beitragstitel.
        markdown_content: Beitragsinhalt als Markdown.
        status: Beitragsstatus.
        category_names: Optionale Kategorie-Namen.
        tag_names: Optionale Tag-Namen.
        featured_image_urls: Optionale Bild-URLs in Fallback-Reihenfolge
            (z.B. ``[maxres, hq, sd]``) für das Beitragsbild.
        video_id: Optionale Video-ID für einen sprechenden Media-Dateinamen.

    Returns:
        Tupel ``(post_id, link, image_warning)``. ``image_warning`` ist ``None``
        bei Erfolg (oder wenn kein Bild gewünscht war), sonst eine Klartext-
        Warnung, dass das Beitragsbild nicht gesetzt werden konnte.

    Raises:
        WordPressError: Bei API-/Netzwerkfehlern beim Beitrag selbst.
        RuntimeError: Wenn das ``markdown``-Paket fehlt.
    """
    client = WordPressClient(config, app_password)
    html = markdown_to_html(markdown_content)
    category_ids = client.resolve_terms(category_names or [], "categories")
    tag_ids = client.resolve_terms(tag_names or [], "tags")

    # Beitragsbild (optional, nicht fatal): Bild laden -> Mediathek -> media_id.
    featured_media: Optional[int] = None
    image_warning: Optional[str] = None
    if featured_image_urls:
        try:
            image_bytes = _download_thumbnail(featured_image_urls)
            if image_bytes is None:
                image_warning = (
                    "Beitragsbild übersprungen: kein Thumbnail erreichbar."
                )
                logger.warning(image_warning)
            else:
                filename = f"somas-thumbnail-{video_id or 'video'}.jpg"
                featured_media = client.upload_media(image_bytes, filename)
        except WordPressError as exc:
            # Upload-Fehler (z.B. fehlende upload_files-Rechte) nicht fatal.
            featured_media = None
            image_warning = f"Beitragsbild konnte nicht gesetzt werden: {exc}"
            logger.warning(image_warning)

    post_id, link = client.post(
        title=title,
        html_content=html,
        status=status,
        category_ids=category_ids or None,
        tag_ids=tag_ids or None,
        featured_media=featured_media,
    )
    return post_id, link, image_warning
