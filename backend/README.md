# HearBeat Backend

Python analysis engine for extracting bass, beat, and drum events from music. Built with FastAPI, Essentia, and Demucs.

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Start dev server
uvicorn hearbeat.main:app --reload --port 8000

# Run tests
pytest tests/ -v
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/analyze` | Upload and analyze audio file |
| GET | `/analysis/{job_id}` | Get analysis result |
| GET | `/analysis/{job_id}/audio` | Serve original audio |
| GET | `/analysis/{job_id}/haptic` | Generate haptic timeline |
| POST | `/auth/login` | Google OAuth login redirect |
| GET | `/auth/me` | Get current user |
| POST | `/auth/logout` | Clear session |
| GET | `/library/songs` | List saved songs |
| POST | `/library/songs` | Save song to library |
| GET | `/library/presets` | List haptic presets |
| POST | `/library/presets` | Save custom preset |

## Deployment

See [GCP_DEPLOY.md](../GCP_DEPLOY.md) for Cloud Run deployment.

Quick start:

```bash
docker build -t hearbeat-api .
docker run -p 8000:8000 hearbeat-api
```

## Environment Variables

See [config.py](src/hearbeat/config.py) for all configuration options.
