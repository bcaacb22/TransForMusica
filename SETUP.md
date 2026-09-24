# Transformusic — Setup Guide

## Prerequisites

- Python 3.11
- Node.js 18+ and Yarn
- MongoDB (running locally on port 27017)
- LM Studio on port 1234 with a model loaded — OR Ollama on port 11434

## Backend

### Windows
```
cd backend
install.bat
.venv\Scripts\activate
python run_app.py
```

### macOS / Linux
```bash
cd backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements-core.txt -r requirements-audio.txt
pip install basic-pitch
python run_app.py
```

Server starts at **http://localhost:8000**  
API docs at **http://localhost:8000/docs**

### Environment Variables (`backend/.env`)

| Variable | Default | Purpose |
|----------|---------|---------|
| `MONGO_URL` | `mongodb://localhost:27017` | MongoDB connection string |
| `DB_NAME` | `transformusic_db` | Database name |
| `CORS_ORIGINS` | `http://localhost:3200` | Allowed CORS origins (comma-separated) |
| `LLM_BASE_URL` | `http://localhost:1234` | LM Studio / Ollama / any OpenAI-compatible LLM |
| `LLM_MODEL` | *(empty = use loaded model)* | Model name to request |
| `AUDD_API_KEY` | — | AuDD.io API key for legal scan (Gateway 01) |
| `DEMUCS_URL` | *(empty = local CPU)* | Remote Demucs GPU server URL (e.g. `http://100.119.105.73:8600`) |
| `VOICE_CLONE_URL` | *(empty = local F5-TTS)* | Remote voice clone server URL (e.g. `http://100.119.105.73:8500`) |

## Frontend

```bash
cd frontend
yarn install
yarn dev
```

Opens at **http://localhost:3200**

### Environment Variables (`frontend/.env`)

| Variable | Default | Purpose |
|----------|---------|---------|
| `VITE_DEV_PORT` | `3200` | Vite dev server port |
| `VITE_BACKEND_URL` | `http://localhost:8000` | Backend base URL for the `/api` dev proxy |

## Quick Start

1. `mongod` — start MongoDB
2. Start LM Studio with a model loaded (port 1234)
3. `cd backend && python run_app.py`
4. `cd frontend && yarn dev`
5. Open http://localhost:3200

## Remote GPU Services (optional)

Both services are optional. If not configured, the app falls back to local CPU processing.

### Demucs (stem separation)
Run `demucs_server.py` on the Windows GPU machine:
```
python demucs_server.py
```
Set `DEMUCS_URL=http://<tailscale-ip>:8600` in `backend/.env`.

### Voice Clone (Gateway 05)
Requires a separate TTS server speaking the `/health` + `/clone` wire contract —
run either `backend/xtts_server.py` (XTTS-v2) or `backend/f5tts_server.py` (F5-TTS)
on the GPU machine, then set `VOICE_CLONE_URL=http://<tailscale-ip>:8500` in `backend/.env`.
Without it, Gateway 05 UI is fully wired but the clone trigger returns
`503 Voice clone service is not configured`.

## Gateway Pipeline

| Gateway | Name | Status |
|---------|------|--------|
| 01 | Legal Diagnostic | Live — AuDD.io fingerprint scan (requires `AUDD_API_KEY`) |
| 02 | Deconstruction | **Live** — stem separation (Demucs) + MIDI (Basic Pitch) + MusicXML (music21) |
| 03 | Morph Engine | **Live** — deterministic DSP morph (`morph_engine.py`): tempo/pitch from similarity target, key/BPM override, measured achieved similarity |
| 04 | Lyric Rebuild | **Live** — LLM lyric generation, style presets/user styles/learned fingerprint, CADENCE vs FRESH structure modes |
| 05 | Voice Clone | UI live, backend live — requires `VOICE_CLONE_URL` (XTTS/F5-TTS server); 503 until configured |

## Fork Ports

This fork runs alongside the original app via `start-fork.bat`:
backend **8001** (`RUN_PORT`), frontend **3201** (`frontend/.env`: `VITE_DEV_PORT`,
`VITE_BACKEND_URL=http://localhost:8001`; the Vite proxy forwards `/api`, so the
browser origin stays 3201 and `CORS_ORIGINS` needs no change).
