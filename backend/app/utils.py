"""
Utility functions for NormoScan.
"""
import re
from typing import Optional


def clean_url(raw: Optional[str]) -> Optional[str]:
    """
    Clean URL from markdown artifacts, brackets, and extra characters.
    
    Handles:
    - Markdown links: [text](url) -> url
    - Bare URLs with brackets: [url] -> url
    - Trailing punctuation: url. -> url
    - Whitespace
    
    Returns None if input is empty/invalid.
    """
    if not raw or not isinstance(raw, str):
        return None
    
    raw = raw.strip()
    if not raw or raw in ("", "null", "None", "[]", "()"):
        return None
    
    # Extract URL from markdown [text](url) or bare URL
    urls = re.findall(r"https?://[^\s\]\)\"']+", raw)
    if urls:
        return urls[-1].strip().rstrip(".,)")
    
    # Fallback: clean brackets
    return raw.strip().strip("[]()").strip()


def truncate_text(text: str, max_length: int = 1000, suffix: str = "...") -> str:
    """Truncate text to max_length, adding suffix if truncated."""
    if not text or len(text) <= max_length:
        return text or ""
    return text[:max_length - len(suffix)] + suffix


def safe_json_loads(data: str, default=None):
    """Safely load JSON string, returning default on error."""
    import json
    try:
        return json.loads(data)
    except (json.JSONDecodeError, TypeError):
        return default


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"
