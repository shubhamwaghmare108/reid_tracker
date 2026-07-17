from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class Detection:
    box: tuple[int, int, int, int]
    confidence: float


class PersonDetector:
    """YOLO person detector with Ultralytics' persistent ByteTrack integration."""
    def __init__(self, model_name: str, confidence: float = 0.35, device: str = "") -> None:
        from ultralytics import YOLO
        self.model = YOLO(model_name)
        self.confidence, self.device = confidence, device

    def track(self, frame: np.ndarray) -> list["TrackedDetection"]:
        """Detect people and associate them with ByteTrack IDs across frames."""
        # ``persist=True`` retains ByteTrack state between calls for one input stream.
        result = self.model.track(
            frame,
            classes=[0],
            conf=self.confidence,
            device=self.device,
            tracker="bytetrack.yaml",
            persist=True,
            verbose=False,
        )[0]
        if result.boxes is None:
            return []
        boxes = result.boxes.xyxy.cpu().numpy().astype(int)
        scores = result.boxes.conf.cpu().numpy()
        track_ids = result.boxes.id
        if track_ids is None:
            return []

        # Local import prevents a module-level circular dependency with Detection.
        from app.tracker.tracker import TrackedDetection

        return [
            TrackedDetection(tuple(map(int, box)), float(score), int(track_id))
            for box, score, track_id in zip(boxes, scores, track_ids.int().cpu().tolist())
        ]
