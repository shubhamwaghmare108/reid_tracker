"""Runtime configuration for the person re-identification pipeline."""
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Settings:
    project_root: Path = Path(__file__).resolve().parents[2]
    detector_model: str = "yolo11n.pt"
    reid_model: str = "osnet_x1_0"
    reid_weights: str = "market1501"
    device: str = ""
    confidence: float = 0.35
    match_threshold: float = 0.58
    gallery_dir: Path | None = None
    output_dir: Path | None = None

    def __post_init__(self) -> None:
        self.gallery_dir = self.gallery_dir or self.project_root / "known_people"
        self.output_dir = self.output_dir or self.project_root / "output"
