# HearBeat

Stage 1: Bass and Beat Musical Event Extraction Engine.

A research backend and professional visualization frontend for extracting meaningful bass and beat events from music files. Built for musicians with hearing loss who need visual analysis of musical rhythm and bass content.

## Architecture

```
hearbeat/
  backend/    Python analysis engine
  frontend/   Next.js visualization workspace
  docs/       Runtime documentation
```

```
Music File
    |
    v
HearBeat Analysis Engine (Python)
    +-- FFmpeg (audio extraction)
    +-- Essentia (beat detection)
    +-- Demucs (bass source separation)
    +-- NumPy/SciPy (signal processing)
    |
    v
JSON Analysis Result
    |
    v
HearBeat Visualization Workspace (Next.js)
    +-- Timeline with beat/bass markers
    +-- Event inspector with filtering
    +-- Diagnostic playback controls
    +-- JSON inspector
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

## Documentation

- [Runtime Architecture](docs/RUNTIME.md) - Complete system documentation
- [Backend README](backend/README.md) - Backend details
- [Frontend README](frontend/README.md) - Frontend details

## Testing

```bash
# Backend tests
cd backend && pytest tests/ -v

# Frontend build
cd frontend && npm run build
```
