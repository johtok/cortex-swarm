"""Context compression between DAG nodes.

Ported from context-distillation-orchestrator. Reduces context size
to prevent context rot and reduce token costs when passing data
between nodes.

Methods:
- extractive: Keep first + last portions (most info-dense)
- key_points: Extract headers, bullets, file paths
- summary: Truncation with intelligent boundaries
"""

from __future__ import annotations


def compress_context(text: str, method: str, level: float = 0.3) -> str:
    """Compress context passed between DAG nodes.

    Args:
        text: The text to compress.
        method: Compression method (none, extractive, key_points, summary).
        level: Compression aggressiveness 0.0-1.0 (higher = more compression).

    Returns:
        Compressed text.
    """
    if method == "none" or not text:
        return text

    max_chars = int(len(text) * (1.0 - level))
    max_chars = max(max_chars, 200)

    if method == "extractive":
        return _extractive(text, max_chars)
    elif method == "key_points":
        return _key_points(text, max_chars)
    else:  # "summary" — truncation with boundary awareness
        return _summary(text, max_chars)


def _extractive(text: str, max_chars: int) -> str:
    """Keep first and last portions (most info-dense)."""
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    return text[:half] + "\n\n[... compressed ...]\n\n" + text[-half:]


def _key_points(text: str, max_chars: int) -> str:
    """Extract lines that look like key information."""
    lines = text.split("\n")
    key_lines = [
        line for line in lines
        if line.strip().startswith(("#", "-", "*", "/", "src/", "def ", "class ", "fn ", "func "))
        or ":" in line[:50]
        or line.strip().startswith(("error", "Error", "ERROR", "warning", "Warning"))
    ]
    result = "\n".join(key_lines)
    if len(result) > max_chars:
        return result[:max_chars]
    return result if result else _summary(text, max_chars)


def _summary(text: str, max_chars: int) -> str:
    """Smart truncation: try to break at paragraph or sentence boundaries."""
    if len(text) <= max_chars:
        return text

    # Try to break at a paragraph boundary
    truncated = text[:max_chars]
    last_para = truncated.rfind("\n\n")
    if last_para > max_chars * 0.7:
        return truncated[:last_para] + "\n\n[... truncated ...]"

    # Try to break at a sentence boundary
    last_period = truncated.rfind(". ")
    if last_period > max_chars * 0.7:
        return truncated[:last_period + 1] + "\n\n[... truncated ...]"

    return truncated + "\n\n[... truncated ...]"
