# Person Re-Identification System

YOLO11 person detection, ID tracking, OSNet embeddings, and cosine similarity matching.

Install dependencies:

```powershell
pip install -r requirements.txt
```

Enroll people with multiple images per folder:

```text
known_people/alice/photo1.jpg
known_people/alice/photo2.jpg
known_people/bob/photo1.jpg
```

Run on an image, video, or webcam:

```powershell
python main.py data\input.mp4 --show
python main.py data\photo.jpg
python main.py 0 --show
```

Annotated media is written to `output/`. Increase `--threshold` (default `0.58`) for stricter matches.
Known-person labels are compact; a top-left panel shows accumulated on-camera
time and `IN`/`OUT` counts for the current run. These are identity-level values, so they remain
combined if ByteTrack assigns a new track ID after an occlusion. Short
detection dropouts (under one second) are treated as the same visit rather
than extra `OUT`/`IN` events.

Pipeline

YOLO11
    ↓
ByteTrack
    ↓
OSNet
    ↓
Cosine Similarity
    ↓
Known / Unknown

