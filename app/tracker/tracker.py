from __future__ import annotations

from dataclasses import dataclass
from app.detector.detector import Detection


@dataclass(frozen=True)
class TrackedDetection(Detection):
    track_id: int


class IoUTracker:
    """Lightweight tracker for stable IDs without external tracking dependencies."""
    def __init__(self, iou_threshold: float = 0.3, max_age: int = 30) -> None:
        self.iou_threshold, self.max_age = iou_threshold, max_age
        self._tracks: dict[int, tuple[tuple[int, int, int, int], int]] = {}
        self._next_id = 1

    @staticmethod
    def _iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
        x1, y1 = max(a[0], b[0]), max(a[1], b[1])
        x2, y2 = min(a[2], b[2]), min(a[3], b[3])
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        union = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - inter
        return inter / union if union else 0.0

    def update(self, detections: list[Detection]) -> list[TrackedDetection]:
        self._tracks = {tid: (box, age + 1) for tid, (box, age) in self._tracks.items() if age + 1 <= self.max_age}
        available = set(self._tracks)
        output = []
        for detection in sorted(detections, key=lambda d: d.confidence, reverse=True):
            best = max(available, key=lambda tid: self._iou(detection.box, self._tracks[tid][0]), default=None)
            if best is not None and self._iou(detection.box, self._tracks[best][0]) >= self.iou_threshold:
                track_id = best
                available.remove(best)
            else:
                track_id, self._next_id = self._next_id, self._next_id + 1
            self._tracks[track_id] = (detection.box, 0)
            output.append(TrackedDetection(detection.box, detection.confidence, track_id))
        return output
