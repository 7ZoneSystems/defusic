# HearBeat

<p align="center">
  <img src="image.png" alt="HearBeat icon" width="120">
</p>

<p align="center"><strong>Feel the rhythm. See the pattern.</strong></p>

<p align="center">
  <img src="https://img.shields.io/badge/Next.js-000000?style=flat&logo=next.js&logoColor=white" alt="Next.js">
  <img src="https://img.shields.io/badge/React-20232A?style=flat&logo=react&logoColor=61DAFB" alt="React">
  <img src="https://img.shields.io/badge/TypeScript-3178C6?style=flat&logo=typescript&logoColor=white" alt="TypeScript">
  <img src="https://img.shields.io/badge/Turbopack-000000?style=flat&logo=turbopack&logoColor=white" alt="Turbopack">
  <img src="https://img.shields.io/badge/Node.js-339933?style=flat&logo=node.js&logoColor=white" alt="Node.js">
  <img src="https://img.shields.io/badge/FastAPI-005571?style=flat&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Python-3776AB?style=flat&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Demucs-4B0082?style=flat&logo=meta&logoColor=white" alt="Demucs">
  <img src="https://img.shields.io/badge/Essentia-8A2BE2?style=flat" alt="Essentia">
  <img src="https://img.shields.io/badge/PyTorch-EE4C2C?style=flat&logo=pytorch&logoColor=white" alt="PyTorch">
  <img src="https://img.shields.io/badge/FFmpeg-007808?style=flat&logo=ffmpeg&logoColor=white" alt="FFmpeg">
  <img src="https://img.shields.io/badge/Google_Drive-4285F4?style=flat&logo=googledrive&logoColor=white" alt="Google Drive">
  <img src="https://img.shields.io/badge/Vercel-000000?style=flat&logo=vercel&logoColor=white" alt="Vercel">
  <img src="https://img.shields.io/badge/Google_Cloud-4285F4?style=flat&logo=googlecloud&logoColor=white" alt="Google Cloud">
</p>

HearBeat is an audio analysis and haptic-translation web app for people who are deaf or hard of hearing, musicians, and drummers. It turns the rhythmic structure of an uploaded track into visual events, diagnostic audio, and browser haptic feedback so beats can be explored through more than hearing alone.

## What Is Built

- Upload supported audio and analyze it in **Music** or **Drumming** mode.
- Detect beats, BPM, bass events, drum onsets, and classified kick, snare, and hi-hat events.
- Separate bass, drums, vocals, and other stems with Demucs, then combine model output with signal-processing analysis.
- Explore waveforms, timelines, event inspectors, drum patterns, metrics, and diagnostic/click-track audio.
- Map detected events to a timed haptic timeline and play it alongside the original track where the browser supports vibration.
- Sign in with Google, connect Google Drive, save songs and analysis metadata, manage a library, and save haptic presets.
- Cache the selected local file in browser IndexedDB while the page is active so a file-selection interruption does not immediately discard it.

## Scope And Limitations

This is a working prototype with a real analysis pipeline which can be also run locally and hosted .

| Area | Current status |
| --- | --- |
| Audio analysis | Built: FFmpeg extraction, Essentia beat/onset analysis, Demucs stem separation, NumPy/SciPy feature processing, and mode-specific event fusion. |
| Web experience | Built: Next.js interface, upload flow, playback, visualizations, drumming view, haptic controls, library UI, and theme switching. |
| Google auth and Drive | Implemented through the backend integration; requires configured Cohesivity and Google credentials. |
| Haptics | Browser vibration is used where supported. Desktop feedback is a mock driver, and iOS Safari does not provide the required Vibration API. |
| Analysis jobs | Job metadata and lookup are stored in backend process memory. Generated JSON/audio artifacts and uploaded originals are written under `OUTPUT_DIR`; lookup is not durable across restarts or multiple workers. |
| Tests | Backend unit/component tests exist. 

## Architecture

```text
Next.js + React browser
    |
    | REST API
    v
FastAPI backend
    +-- FFmpeg       decoding and normalization
    +-- Essentia     beat and onset detection
    +-- Demucs       four-stem source separation
    +-- PyTorch      model runtime
    +-- NumPy/SciPy  filtering, envelopes, RMS, and spectral features
    |
    +-- Cohesivity   authentication and database integration
    +-- Google Drive optional user-owned audio storage
```

The frontend runs as a Next.js app and calls the FastAPI service through `NEXT_PUBLIC_API_URL`. The backend returns structured analysis JSON and generates audio diagnostics, waveforms, click tracks, and haptic timelines. Authenticated library records and saved audio use the configured Cohesivity and Google Drive integrations; anonymous analysis is indexed by the backend process and rendered in the browser, with generated artifacts written under `OUTPUT_DIR`.

## Local Setup

### Prerequisites

- Python 3.11 or newer
- Node.js and npm
- FFmpeg available on `PATH`
- A machine with enough memory for PyTorch and Demucs; GPU acceleration is optional

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Download/cache the Demucs model once when needed.
python setup_models.py

uvicorn hearbeat.main:app --reload --port 8000
```

### Frontend

In `frontend/.env.local`, set:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Then run:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000` and upload an MP3, WAV, FLAC, OGG, AAC, M4A, MP4, WMA, or WebM file.

### Optional Integrations

Google sign-in, Drive storage, and the persistent library need server-side configuration. Set the Cohesivity variables, `GOOGLE_DRIVE_CLIENT_ID`, `GOOGLE_DRIVE_CLIENT_SECRET`, `DRIVE_TOKEN_ENCRYPTION_KEY`, and `FRONTEND_URL` in the backend environment. Set `NEXT_PUBLIC_GOOGLE_DRIVE_CLIENT_ID` in the frontend environment when using Drive OAuth. Keep secrets out of `NEXT_PUBLIC_*` variables.

## Tests And Checks

```bash
cd backend
source .venv/bin/activate
pytest tests/ -v

cd ../frontend
npm run lint
npm run build
```

## Deployment

The intended deployment is Next.js on Vercel and the FastAPI service on Google Cloud Run. The backend container needs FFmpeg, the Demucs model, adequate memory, and configured environment variables. See [GCP_DEPLOY.md](GCP_DEPLOY.md) for the deployment commands and resource settings. Review the process-local job-store limitation before using multiple Cloud Run workers or instances.

## Repository Guide

- [Runtime architecture](docs/RUNTIME.md)
- [Backend API and development notes](backend/README.md)
- [Frontend development and Vercel notes](frontend/README.md)
- [Deployment guide](GCP_DEPLOY.md)
- [Privacy policy](frontend/app/privacy/page.tsx)
- [Terms of service](frontend/app/terms/page.tsx)

## Origin

HearBeat began as a promise to a friend with congenital hearing loss who loved music and drums but could not reliably access low frequencies through hearing devices. The project explores a small, practical starting point: using a phone's vibration motor alongside visual and audio analysis to make rhythmic information easier to feel.