import re

MIN_ALPHA_RATIO = 0.65
MIN_WORDS = 10


def _strip_html_noise(text: str) -> str:
    cleaned = re.sub(r"<div>.*?</div>", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"<[^>]+>", "", cleaned)
    return cleaned.strip()


def _alpha_ratio(text: str) -> float:
    alphanumeric_count = sum(c.isalnum() for c in text)
    total_count = len(text) or 1
    return alphanumeric_count / total_count


def clean_chunk(text: str) -> str:
    """Stage-1 deterministic heuristics: strip inline HTML noise, drop code-like text.

    Returns cleaned text, or "" if the chunk is dropped.
    """
    if not text:
        return ""
    cleaned = _strip_html_noise(text)
    if not cleaned:
        return ""
    if _alpha_ratio(cleaned) < MIN_ALPHA_RATIO:
        return ""
    if len(cleaned.split()) < MIN_WORDS:
        return ""
    return cleaned
