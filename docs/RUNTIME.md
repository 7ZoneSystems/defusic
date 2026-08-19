# Runtime Architecture

## Repository Structure

```
hearbeat/
  backend/          Python analysis engine (FastAPI + Essentia + Demucs)
  frontend/         Next.js visualization workspace
  docs/             Documentation
```

## Architecture Diagram

```
Browser (localhost:3000)
    |
    | HTTPS / HTTP
    v
Next.js Frontend
    |
    | REST API (fetch)
    v
FastAPI Backend (localhost:8000)
    |
    +-- FFmpeg         Audio extraction & normalization
    +-- Essentia       Beat detection (RhythmExtractor2013) + Onset detection (HFC)
    +-- Demucs         Source separation (bass, drums, vocals, other)
    +-- NumPy/SciPy    Signal processing (RMS, onset, spectral flux)
    +-- SoundFile      WAV I/O
    |
    v
JSON Analysis Result (v0.1 music / v0.2 drumming)
    |
    v
Browser renders timeline, events, metrics, waveforms
```

## Backend Startup

```bash
cd backend

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Download models (run once)
python setup_models.py

# Start the API server
uvicorn hearbeat.main:app --reload --port 8000
```

The backend will be available at `http://localhost:8000`.

### CLI Usage

```bash
cd backend
source .venv/bin/activate

# Analyze a track (music mode)
python analyze.py ../test_audio/song.mp3

# Analyze with verbose output
python analyze.py ../test_audio/song.mp3 -v

# Save click track
python analyze.py ../test_audio/song.mp3 --save-click-track outputs/clicks.wav

# Play through speakers
python analyze.py ../test_audio/song.mp3 --play
```

### Running Tests

```bash
cd backend
source .venv/bin/activate
pytest tests/ -v
```

## Frontend Startup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The frontend will be available at `http://localhost:3000`.

### Build for Production

```bash
cd frontend
npm run build
npm start
```

## Environment Variables

### Backend (`backend/.env`)

| Variable | Default | Description |
|---|---|---|
| `FFMPEG_PATH` | `ffmpeg` | Path to FFmpeg binary |
| `OUTPUT_DIR` | `./outputs` | Where JSON/WAV outputs are saved |
| `MODELS_DIR` | `./models` | Local models directory (run `setup_models.py`) |
| `DEMUCS_MODEL` | `htdemucs` | Demucs model for source separation |
| `DEVICE` | `cpu` | PyTorch device (`cpu`, `cuda`, `mps`) |
| `ANALYSIS_SAMPLE_RATE` | `44100` | Audio sample rate for analysis |
| `API_HOST` | `0.0.0.0` | API bind address |
| `API_PORT` | `8000` | API port |
| `MAX_UPLOAD_MB` | `100` | Maximum upload size in MB |

### Frontend (`frontend/.env.local`)

| Variable | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend API URL |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `POST` | `/analyze?mode=music` | Upload and analyze (music mode) |
| `POST` | `/analyze?mode=drumming` | Upload and analyze (drumming mode) |
| `GET` | `/analysis/{job_id}` | Get analysis result |
| `GET` | `/analysis/{job_id}/json` | Download raw JSON |
| `GET` | `/analysis/{job_id}/audio` | Serve original uploaded audio |
| `GET` | `/analysis/{job_id}/diagnostic?layers=all` | Generate diagnostic audio |
| `GET` | `/analysis/{job_id}/waveform?resolution=2000` | Get downsampled waveform data |
| `GET` | `/analysis/{job_id}/click-track` | Download beat click WAV |
| `GET` | `/analysis/{job_id}/click-track?multi=true` | Download multi-layer WAV |
| `GET` | `/visualize/{job_id}` | HTML debug visualization |

## Analysis Modes

### Music Enjoyment (v0.1)

Stage 1 pipeline unchanged:

1. Audio extraction via FFmpeg
2. Beat detection via Essentia RhythmExtractor2013
3. Source separation via Demucs (bass stem)
4. Bass event detection (RMS + onset strength)
5. Event fusion (beat/bass relationships)
6. Diagnostic audio generation

Events: `beat`, `bass`, `bass_beat`, `bass_offbeat`, `bass_accent`

### Drumming (v0.2)

New drum-focused pipeline:

1. Audio extraction via FFmpeg
2. Beat detection via Essentia RhythmExtractor2013
3. Source separation via Demucs (all stems: bass, drums, vocals, other)
4. Drum onset detection via Essentia OnsetDetection (HFC)
5. Spectral feature extraction (centroid, bandwidth, band energies)
6. Event classification (kick, snare, hihat, drum_onset)
7. Beat alignment (nearest beat, delta, position)
8. Diagnostic audio generation (synthetic sounds)

Events: `beat`, `kick`, `snare`, `hihat`, `drum_onset`, `bass`

## File Flow

1. User uploads MP3/MP4 via frontend
2. Frontend sends file to `POST /analyze?mode=music|drumming`
3. Backend saves upload to temp directory
4. FFmpeg extracts audio to normalized WAV (44.1kHz, mono, float32)
5. Essentia detects beats (BPM, timestamps, confidence)
6. Demucs separates all stems (bass, drums, vocals, other)
7. Mode-specific analysis runs (bass events or drum onset detection)
8. Event fusion computes temporal relationships
9. JSON result returned to frontend
10. Frontend renders timeline, metrics, events, waveforms

### Temporary Files

- Uploaded files: system temp directory (deleted after analysis)
- Normalized WAV: system temp directory (deleted after analysis)
- Original audio: `backend/outputs/{filename}` (kept for playback)
- Output JSON: `backend/outputs/{filename}.json`
- Click track WAVs: `backend/outputs/{filename}_clicks.wav`
- Diagnostic WAVs: `backend/outputs/{filename}_diagnostic_*.wav`

## Model Requirements

### Setup (run once)

```bash
cd backend
source .venv/bin/activate
python setup_models.py
```

This downloads models to `backend/models/` for offline use. No network access required after setup.

### Demucs (htdemucs)

- **Model**: `htdemucs` (pre-trained, 4-stem separation)
- **Location**: `backend/models/` (local, deterministic)
- **Files**: `htdemucs.yaml` + `955717e8.safetensors` (~80MB)
- **License**: MIT (Facebook Research)
- **CPU**: Works, ~60s for 3-minute track
- **GPU**: Recommended for faster processing

### Essentia

- **Algorithms**: RhythmExtractor2013 (multifeature), OnsetDetection (HFC)
- **License**: AGPL-3.0
- **No model download required**

## Troubleshooting

### Backend unavailable

Ensure the backend is running:
```bash
cd backend
source .venv/bin/activate
uvicorn hearbeat.main:app --reload --port 8000
```

### CORS errors

The backend allows all origins by default. If you modify this, ensure the frontend origin is allowed.

### FFmpeg missing

Install FFmpeg:
```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg
```

### Model download fails

Demucs models are downloaded from Hugging Face Hub on first use. Ensure internet access. The model is cached after first download.

### GPU unavailable

The system falls back to CPU automatically. Set `DEVICE=cpu` in `backend/.env` to suppress warnings.

### Port conflicts

Change the port in `backend/.env`:
```
API_PORT=8001
```

Then update `frontend/.env.local`:
```
NEXT_PUBLIC_API_URL=http://localhost:8001
```

### Large file failures

Increase `MAX_UPLOAD_MB` in `backend/.env`:
```
MAX_UPLOAD_MB=500
```

### Frontend API URL problems

Ensure `NEXT_PUBLIC_API_URL` in `frontend/.env.local` matches the backend URL. Restart the frontend dev server after changing environment variables.
