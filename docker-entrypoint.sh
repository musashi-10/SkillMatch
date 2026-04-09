#!/bin/sh
set -e
cd /app

export SKILLMATCH_DATA_DIR="${SKILLMATCH_DATA_DIR:-/app/data}"
mkdir -p "$SKILLMATCH_DATA_DIR"

python create_db.py

python - <<'PY' || true
import nltk
for p in ("punkt", "punkt_tab", "stopwords"):
    try:
        nltk.download(p, quiet=True)
    except Exception:
        pass
PY

PORT="${PORT:-8000}"
exec uvicorn main12:app --host 0.0.0.0 --port "$PORT"
