"""Business-Logik für den SOMAS Prompt Generator."""

from src.core.youtube_client import get_video_info, get_transcript, extract_video_id
from src.core.prompt_builder import build_prompt
from src.core.linkedin_formatter import format_for_linkedin
from src.core.export import export_to_markdown

__all__ = [
    "get_video_info",
    "get_transcript",
    "extract_video_id",
    "build_prompt",
    "format_for_linkedin",
    "export_to_markdown",
]
