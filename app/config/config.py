"""Runtime configuration for the person re-identification pipeline."""
from dataclasses import dataclass
import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime
from zoneinfo import ZoneInfo


# Load local development credentials before Settings reads environment variables.
# Existing system environment values still take precedence over .env values.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")


def database_timestamp() -> datetime:
    """Return the configured local wall-clock time for MySQL DATETIME fields."""
    timezone_name = os.getenv("REID_TIMEZONE", "Asia/Kolkata")
    return datetime.now(ZoneInfo(timezone_name)).replace(tzinfo=None)


@dataclass
class Settings:
    project_root: Path = Path(__file__).resolve().parents[2]
    detector_model: str = "yolo11n.pt"
    reid_model: str = "osnet_x1_0"
    reid_weights: str = "market1501"
    device: str = ""
    confidence: float = 0.35
    match_threshold: float = 0.58
    known_retention_threshold: float = float(os.getenv("REID_KNOWN_RETENTION_THRESHOLD", "0.45"))
    gallery_dir: Path | None = None
    output_dir: Path | None = None
    mysql_host: str = os.getenv("REID_MYSQL_HOST", "localhost")
    mysql_port: int = int(os.getenv("REID_MYSQL_PORT", "3306"))
    mysql_user: str = os.getenv("REID_MYSQL_USER", "root")
    mysql_password: str = os.getenv("REID_MYSQL_PASSWORD", "")
    mysql_database: str = os.getenv("REID_MYSQL_DATABASE", "person_reid")

    def __post_init__(self) -> None:
        self.gallery_dir = self.gallery_dir or self.project_root / "known_people"
        self.output_dir = self.output_dir or self.project_root / "output"
