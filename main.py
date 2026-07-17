"""Run person re-identification on an image, video, or webcam."""
from __future__ import annotations
import argparse
from pathlib import Path
import time
import cv2
from app.config.config import Settings
from app.database.database import Gallery
from app.detector.detector import PersonDetector
from app.reid.reid import FeatureExtractor
from app.services.matcher import CosineMatcher
from app.services.presence import PresenceTracker
from app.utils.utils import crop_box, draw_label, draw_presence_panel


def process_frame(frame, detector, extractor, matcher, cache, presence, elapsed: float = 0.0):
    """Annotate a frame and account for known identities' camera presence."""
    tracks = detector.track(frame)
    resolved_tracks = []
    for track in tracks:
        if track.track_id not in cache or cache[track.track_id][2] % 15 == 0:
            crop = crop_box(frame, track.box)
            if crop is not None:
                try: cache[track.track_id] = (matcher.match(extractor.extract(crop)), track.box, 1)
                except ValueError: continue
        elif track.track_id in cache:
            match, _, age = cache[track.track_id]; cache[track.track_id] = (match, track.box, age + 1)
        if track.track_id in cache:
            match = cache[track.track_id][0]
            resolved_tracks.append((track, match))

    # Sets prevent duplicate entries/time when multiple tracks match one identity.
    known_names = {match.name for _, match in resolved_tracks if match.known}
    presence.update(known_names, elapsed)
    for track, match in resolved_tracks:
        if match.known:
            draw_label(
                frame,
                track.box,
                f"{match.name} #{track.track_id}",
                True,
            )
        else:
            draw_label(frame, track.box, f"Unknown #{track.track_id}", False)
    draw_presence_panel(frame, presence.records, presence.active_names)
    return frame


def run(source: str | int, settings: Settings, show: bool = False) -> Path:
    input_path = Path(str(source))
    if isinstance(source, str) and not input_path.is_file():
        raise FileNotFoundError(
            f"Input file was not found: {input_path.resolve()}\n"
            "Copy a supported image/video into data/ or pass its full path."
        )
    image_mode = isinstance(source, str) and input_path.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
    # Validate the source before initializing/downloading models.
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        cap.release()
        raise RuntimeError(f"OpenCV could not decode input: {input_path.resolve()}")

    extractor = FeatureExtractor(settings.reid_model, settings.reid_weights, settings.device)
    gallery = Gallery.load(settings.gallery_dir, extractor)
    print(f"Loaded {len(gallery.names)} identities from {settings.gallery_dir}")
    detector = PersonDetector(settings.detector_model, settings.confidence, settings.device)
    matcher, cache, presence = CosineMatcher(gallery, settings.match_threshold), {}, PresenceTracker()
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    if image_mode:
        ok, frame = cap.read(); cap.release()
        if not ok: raise RuntimeError("Could not read image")
        output = settings.output_dir / f"{input_path.stem}_reid.jpg"
        cv2.imwrite(str(output), process_frame(frame, detector, extractor, matcher, cache, presence)); return output
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0; width, height = int(cap.get(3)), int(cap.get(4))
    output = settings.output_dir / "reid_output.mp4"
    writer = cv2.VideoWriter(str(output), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    previous_timestamp = None
    while True:
        ok, frame = cap.read()
        if not ok: break
        # POS_MSEC is reliable for files; webcams generally report zero, so use
        # a monotonic clock for live camera sources.
        timestamp = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000.0
        if isinstance(source, int) or timestamp <= 0:
            timestamp = time.monotonic()
        elapsed = 0.0 if previous_timestamp is None else timestamp - previous_timestamp
        previous_timestamp = timestamp
        annotated = process_frame(frame, detector, extractor, matcher, cache, presence, elapsed); writer.write(annotated)
        if show:
            cv2.imshow("Person ReID", annotated)
            if cv2.waitKey(1) & 0xFF in (27, ord("q")): break
    cap.release(); writer.release(); cv2.destroyAllWindows(); return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="YOLO + OSNet person re-identification")
    parser.add_argument("source", help="Path to image/video, or webcam index such as 0")
    parser.add_argument("--show", action="store_true")
    parser.add_argument("--threshold", type=float, default=0.58)
    args = parser.parse_args(); source = int(args.source) if args.source.isdigit() else args.source
    print(f"Saved result to {run(source, Settings(match_threshold=args.threshold), args.show)}")
