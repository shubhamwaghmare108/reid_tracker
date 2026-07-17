from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import numpy as np
import cv2
from app.utils.utils import image_files


@dataclass
class Gallery:
    names: list[str]
    embeddings: np.ndarray

    @classmethod
    def load(cls, root: Path, extractor) -> "Gallery":
        names, embeddings = [], []
        root.mkdir(parents=True, exist_ok=True)
        for identity_dir in sorted(p for p in root.iterdir() if p.is_dir()):
            features = [extractor.extract(image) for path in image_files(identity_dir)
                        if (image := cv2.imread(str(path))) is not None]
            if features:
                vector = np.mean(features, axis=0); vector /= np.linalg.norm(vector)
                names.append(identity_dir.name); embeddings.append(vector)
        return cls(names, np.stack(embeddings) if embeddings else np.empty((0, 0), dtype=np.float32))
