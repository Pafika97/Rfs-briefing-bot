import time, hashlib
from typing import List, Tuple
from razdel import sentenize
from sklearn.feature_extraction.text import TfidfVectorizer
import numpy as np

class RollingSummarizer:
    def __init__(self, window_seconds: int = 180):
        self.window_seconds = window_seconds
        self._buffer: List[tuple[float,str]] = []

    def feed_text(self, text: str):
        now = time.time()
        self._buffer.append((now, text))
        self._buffer = [(t, s) for (t, s) in self._buffer if now - t <= self.window_seconds]

    def get_bullets(self, max_bullets: int = 6) -> Tuple[list[str], str]:
        now = time.time()
        self._buffer = [(t, s) for (t, s) in self._buffer if now - t <= self.window_seconds]
        full = " ".join(s for _, s in self._buffer).strip()
        if not full:
            return [], ""
        sents = [s.text.strip() for s in sentenize(full) if len(s.text.strip()) > 20]
        if not sents:
            return [], ""
        vec = TfidfVectorizer(max_features=1000, stop_words="russian")
        X = vec.fit_transform(sents)
        scores = X.sum(axis=1).A.ravel()
        idx = scores.argsort()[::-1][:max_bullets]
        bullets = [sents[i] for i in idx]
        fp = hashlib.md5(("||".join(bullets)).encode()).hexdigest()
        return bullets, fp
