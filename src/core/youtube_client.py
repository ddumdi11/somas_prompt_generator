"""YouTube-Client für Metadaten- und Transkript-Abruf."""

import logging
import re
from typing import Optional

import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound

from src.config.defaults import VideoInfo


logger = logging.getLogger(__name__)


def extract_video_id(url: str) -> Optional[str]:
    """Extrahiert die Video-ID aus einer YouTube-URL.

    Args:
        url: YouTube-URL (verschiedene Formate unterstützt)

    Returns:
        Video-ID oder None bei ungültiger URL
    """
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com/embed/([a-zA-Z0-9_-]{11})',
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def get_video_info(url: str) -> VideoInfo:
    """Holt Metadaten eines YouTube-Videos via yt-dlp.

    Args:
        url: YouTube-URL

    Returns:
        VideoInfo-Objekt mit Titel, Kanal, Dauer und URL

    Raises:
        ValueError: Bei ungültiger URL oder Fehler beim Abruf
    """
    video_id = extract_video_id(url)
    if not video_id:
        raise ValueError(f"Ungültige YouTube-URL: {url}")

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        return VideoInfo(
            title=info.get('title', 'Unbekannter Titel'),
            channel=info.get('uploader', 'Unbekannter Kanal'),
            duration=info.get('duration', 0),
            url=url,
        )
    except Exception as e:
        logger.error(f"Fehler beim Abruf der Metadaten: {e}")
        raise ValueError(f"Konnte Video-Informationen nicht abrufen: {e}")


def get_transcript(url: str, language: str = "de") -> Optional[str]:
    """Holt das Transkript eines YouTube-Videos.

    Args:
        url: YouTube-URL
        language: Bevorzugte Sprache (Standard: "de")

    Returns:
        Transkript als Text oder None falls nicht verfügbar
    """
    video_id = extract_video_id(url)
    if not video_id:
        logger.warning(f"Konnte Video-ID nicht extrahieren: {url}")
        return None

    try:
        # Versuche zuerst die bevorzugte Sprache
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

        try:
            transcript = transcript_list.find_transcript([language])
        except NoTranscriptFound:
            # Fallback: Englisch oder erste verfügbare Sprache
            try:
                transcript = transcript_list.find_transcript(['en'])
            except NoTranscriptFound:
                # Nimm das erste verfügbare Transkript
                transcript = next(iter(transcript_list))

        # Transkript-Einträge zu Text zusammenfügen
        entries = transcript.fetch()
        text_parts = [entry['text'] for entry in entries]
        return ' '.join(text_parts)

    except TranscriptsDisabled:
        logger.warning(f"Transkripte sind für dieses Video deaktiviert: {video_id}")
        return None
    except Exception as e:
        logger.error(f"Fehler beim Abruf des Transkripts: {e}")
        return None
