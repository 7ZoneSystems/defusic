# HearBeat

Music bass/beat/drum analysis engine with haptic feedback for hearing-impaired musicians.

```
hearbeat/
  backend/    Python analysis engine (FastAPI + Essentia + Demucs)
  frontend/   Next.js visualization workspace
  docs/       Runtime documentation
```

## Architecture

```
Audio File
    |
    v
HearBeat Backend (Python/FastAPI)
    +-- FFmpeg (audio extraction)
    +-- Essentia (beat detection)
    +-- Demucs (stem separation)
    +-- NumPy/SciPy (signal processing)
    +-- Cohesivity (auth + database)
    |
    v
JSON Analysis + Haptic Timeline
    |
    v
HearBeat Frontend (Next.js)
    +-- Music mode: playback + haptic visualizers
    +-- Drumming mode: stem analysis + drum detection
    +-- User library (saved tracks, custom presets)
    +-- Google OAuth login
```

## Quick Start

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Start API server
uvicorn hearbeat.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000` and upload an audio file.

## Deployment

### Frontend (Vercel)

1. Push to GitHub
2. Import at [vercel.com/new](https://vercel.com/new)
3. Set `NEXT_PUBLIC_API_URL` to your backend URL
4. Deploy

See [frontend/README.md](frontend/README.md) for details.

### Backend (GCP Cloud Run)

```bash
cd backend
gcloud builds submit --tag gcr.io/$PROJECT_ID/hearbeat-api

gcloud run deploy hearbeat-api \
  --image gcr.io/$PROJECT_ID/hearbeat-api \
  --region us-central1 \
  --allow-unauthenticated \
  --memory 4Gi \
  --cpu 2
```

See [GCP_DEPLOY.md](GCP_DEPLOY.md) for full guide including secrets, GPU, and custom domains.

## Documentation

- [GCP Deployment Guide](GCP_DEPLOY.md) - Backend deployment to Google Cloud
- [Runtime Architecture](docs/RUNTIME.md) - Complete system documentation
- [Backend README](backend/README.md) - Backend details
- [Frontend README](frontend/README.md) - Frontend details

## Testing

```bash
# Backend tests
cd backend && pytest tests/ -v

# Frontend lint + build
cd frontend && npm run lint && npm run build
```
