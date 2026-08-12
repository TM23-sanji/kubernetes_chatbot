import hashlib
import re

_SHINGLE_SIZE = 3
_NUM_HASHES = 16
_BANDS = 4
_ROWS_PER_BAND = _NUM_HASHES // _BANDS
_DUP_THRESHOLD = 0.8

_WORD_RE = re.compile(r"[^a-z0-9 ]+")


def _normalize(text: str) -> str:
    return _WORD_RE.sub(" ", text.lower())


def _shingles(text: str) -> list[str]:
    words = _normalize(text).split()
    return [" ".join(words[i:i + _SHINGLE_SIZE]) for i in range(len(words) - _SHINGLE_SIZE + 1)]


def _signature(text: str) -> list[int]:
    """MinHash signature: per-hash minimum over word-shingle hashes."""
    sig = [None] * _NUM_HASHES
    for shingle in _shingles(text):
        for i in range(_NUM_HASHES):
            h = int(hashlib.md5(f"mh{i}:{shingle}".encode()).hexdigest()[:8], 16)
            if sig[i] is None or h < sig[i]:
                sig[i] = h
    return [s if s is not None else 0 for s in sig]


def _jaccard(sig_a: list[int], sig_b: list[int]) -> float:
    matches = sum(1 for a, b in zip(sig_a, sig_b) if a == b)
    return matches / len(sig_a)


class DedupFilter:
    """Run-scoped near-duplicate detector using MinHash + LSH banding.

    Chunks whose estimated Jaccard similarity to an already-seen chunk is
    >= threshold are considered duplicates and dropped before embedding.
    """

    def __init__(self, threshold: float = _DUP_THRESHOLD):
        self.threshold = threshold
        self._buckets: dict[tuple, list[list[int]]] = {}

    def is_duplicate(self, text: str) -> bool:
        sig = _signature(text)
        for band in range(_BANDS):
            key = (band, tuple(sig[band * _ROWS_PER_BAND:(band + 1) * _ROWS_PER_BAND]))
            for other in self._buckets.get(key, []):
                if _jaccard(sig, other) >= self.threshold:
                    return True
        return False

    def add(self, text: str) -> None:
        sig = _signature(text)
        for band in range(_BANDS):
            key = (band, tuple(sig[band * _ROWS_PER_BAND:(band + 1) * _ROWS_PER_BAND]))
            self._buckets.setdefault(key, []).append(sig)
