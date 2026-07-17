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
For better recognition at different distances, enroll each person with close,
mid-distance, and farther images. A confirmed identity is retained down to the
`REID_KNOWN_RETENTION_THRESHOLD` score (default `0.45`) when it remains the
best match, reducing brief `Unknown` labels from distance or blur.
Known-person labels are compact; a top-left panel shows accumulated on-camera
time and `IN`/`OUT` counts for the current run. These are identity-level values, so they remain
combined if ByteTrack assigns a new track ID after an occlusion. Short
detection dropouts (under one second) are treated as the same visit rather
than extra `OUT`/`IN` events.

## MySQL storage

Each completed run is saved to `reid_runs`, with one per-person summary in
`person_presence`, and every confirmed `IN`/`OUT` event in
`person_presence_events`. Create the database once, then set these variables before
running the app:

```powershell
mysql -u root -p -e "CREATE DATABASE person_reid"
$env:REID_MYSQL_HOST = "localhost"
$env:REID_MYSQL_USER = "root"
$env:REID_MYSQL_PASSWORD = "your-password"
$env:REID_MYSQL_DATABASE = "person_reid"
$env:REID_TIMEZONE = "Asia/Kolkata"
```

The tables are created automatically. Install the new dependency with
`pip install -r requirements.txt`.

## Dashboard

Launch the Streamlit dashboard after processing a camera run:

```powershell
streamlit run streamlit_app.py
```

It reads MySQL and displays completed runs, per-person presence totals, and
the detailed `IN`/`OUT` event timeline.

Set `REID_ADMIN_PASSWORD` in `.env` to enable the password-protected **Admin**
tab. It can enroll reference images for a known person and delete a completed
run with its associated summaries and events. Run deletion is a soft delete:
the records are marked deleted and MySQL triggers copy their original data to
`deleted_reid_runs`, `deleted_person_presence`, and
`deleted_person_presence_events`.

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

