from typing import Optional


def estimate_tokens(text: Optional[str]) -> int:
    """Rough token estimator using ~4 chars/token heuristic.
    Returns at least 1 for any non-empty string.
    """
    if not text:
        return 0
    try:
        length = len(text)
        return max(1, int(length / 4))
    except Exception:
        return 0
