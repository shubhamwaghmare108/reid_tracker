from __future__ import annotations

from dataclasses import dataclass
import numpy as np
from app.database.database import Gallery


@dataclass(frozen=True)
class Match:
    name: str
    score: float
    known: bool
    candidate_name: str = "Unknown"


class CosineMatcher:
    def __init__(self, gallery: Gallery, threshold: float = 0.58) -> None:
        self.gallery, self.threshold = gallery, threshold

    def match(self, embedding: np.ndarray) -> Match:
        if not self.gallery.names:
            return Match("Unknown", 0.0, False, "Unknown")
        scores = self.gallery.embeddings @ embedding
        index = int(np.argmax(scores)); score = float(scores[index])
        candidate_name = self.gallery.names[index]
        return Match(candidate_name if score >= self.threshold else "Unknown", score, score >= self.threshold, candidate_name)
