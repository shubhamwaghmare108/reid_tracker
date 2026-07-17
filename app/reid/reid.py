from __future__ import annotations

import numpy as np


class FeatureExtractor:
    """OSNet embedding extractor with L2-normalized feature vectors."""
    def __init__(self, model_name: str = "osnet_x1_0", weights: str = "market1501", device: str = "") -> None:
        # Different torchreid distributions expose this utility from different
        # module paths. The PyPI ``torchreid-pip`` build uses ``reid.utils``.
        try:
            from torchreid.utils import FeatureExtractor as TorchreidExtractor
        except ModuleNotFoundError:
            from torchreid.reid.utils import FeatureExtractor as TorchreidExtractor
        self._extractor = TorchreidExtractor(model_name=model_name, model_path="", device=device or "cpu", verbose=False)

    def extract(self, image: np.ndarray) -> np.ndarray:
        if image is None or image.size == 0:
            raise ValueError("Cannot extract an embedding from an empty crop")
        # OpenCV provides BGR, whereas the extractor's NumPy path expects RGB.
        feature = self._extractor(image[:, :, ::-1].copy()).cpu().numpy().reshape(-1).astype(np.float32)
        norm = np.linalg.norm(feature)
        return feature / norm if norm else feature
