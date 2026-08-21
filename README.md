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
Browser (Next.js)
    |
    v
Vercel (reverse proxy)
    |
    v
GCP Backend (FastAPI)
    +-- FFmpeg (audio extraction)
    +-- Essentia (beat detection)
    +-- Demucs (stem separation)
    +-- NumPy/SciPy (signal processing)
    |
    +---> Cohesivity (auth + database infrastructure)
    |
    +---> Google Drive (user-owned audio storage, optional)
```

### Data Flow

**Anonymous users (no account):**
```
Audio file
    |
    v
Browser IndexedDB (temporary local cache, single file)
    |
    v
Backend analysis (processed in memory, not stored)
    |
    v
Results returned to browser
```

**Authenticated users (with Google account):**
```
Audio file
    |
    v
Backend analysis
    |
    v
User's Google Drive (HearBeat/Songs/ folder)  <-- saved audio
    |
    v
Cohesivity Postgres (metadata, analysis refs, presets)
```

### What Gets Stored Where

| Storage | Contents | Lifetime |
|---------|----------|----------|
| Browser IndexedDB | Current audio file (single) | Until page reload / new file selected |
| Google Drive | Saved audio files (HearBeat/Songs/) | Until user deletes |
| Cohesivity Postgres | User account, library metadata, haptic presets | Until account deletion |
| Backend memory | In-flight analysis data | Per-request only |

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
4. Set `NEXT_PUBLIC_GOOGLE_DRIVE_CLIENT_ID` for Google Drive integration
5. Deploy

See [frontend/README.md](frontend/README.md) for details.

### Backend (GCP)

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

## Authentication

- Google Sign-In is optional. Core analysis works without an account.
- Authenticated users get a persistent library (saved songs, haptic presets).
- Session cookies are httpOnly, secure, and SameSite=Lax.

## Google Drive Integration (Optional)

- Connects via Google OAuth with the narrow `drive.file` scope.
- Creates a `HearBeat/Songs/` folder in the user's Drive.
- Saved audio files are stored in the user's Drive, not on HearBeat servers.
- Drive access and refresh tokens are encrypted at rest (AES-256-GCM).
- Users can disconnect Drive at any time without losing Drive files.
- Removing a song from HearBeat does not delete it from Drive.

## Privacy and Data

- No analytics, advertising, or tracking services.
- Audio files are processed in memory and not stored permanently on the server.
- Anonymous sessions use browser-only local caching.
- See [Privacy Policy](https://defusic.vercel.app/privacy) and [Terms of Service](https://defusic.vercel.app/terms).

## Security

- All OAuth tokens handled server-side (never exposed to browser).
- Google Drive tokens encrypted at rest with AES-256-GCM.
- No secrets in `NEXT_PUBLIC_*` variables or frontend bundles.
- Cohesivity credentials remain server-side only.

## Documentation

- [Privacy Policy](https://defusic.vercel.app/privacy)
- [Terms of Service](https://defusic.vercel.app/terms)
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

<!-- BEGIN:cohesivity -->
If you are another agent who just picked up this project, you can get the status of its backend using the status endpoint, read more at https://cohesivity.ai/backend-for-ai-agents
<!-- END:cohesivity -->
