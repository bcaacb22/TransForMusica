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
| `REACT_APP_BACKEND_URL` | `http://localhost:8000` | Backend API base URL |

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

### Voice Clone (F5-TTS)
Requires a separate F5-TTS or XTTS server.  
Set `VOICE_CLONE_URL=http://<tailscale-ip>:8500` in `backend/.env`.

## Gateway Pipeline

| Gateway | Name | Status |
|---------|------|--------|
| 01 | Legal Diagnostic | Live — AuDD.io fingerprint scan (requires `AUDD_API_KEY`) |
| 02 | Deconstruction | **Live** — stem separation (Demucs) + MIDI (Basic Pitch) + MusicXML (music21) |
| 03 | Morph Engine | UI only — no beat morphing backend yet |
| 04 | Lyric Rebuild | **Live** — LLM lyric generation with style presets, user styles, learned fingerprint |
| 05 | Voice Clone | Partial — endpoints exist, F5-TTS integration present but untested |
