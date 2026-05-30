# Beat Maker — Product Requirements (PRD)

## Original problem statement
Build a program that turns uploaded instrumentals into original, copyrightable beats,
generates rap lyrics in a chosen style, and allows users to train the AI on samples
of their own work.

"Publish" means formatting everything in a copyrightable, DAW-ready package:
- Uploaded audio is broken into stems (Bass, Kick, Melody, Harmony, Percussion)
- Stems are converted to MIDI and MusicXML
- User can import the MIDI into a DAW and swap instruments → a completely
  transformative, copyrightable original composition

## Core user flow
1. Create a project (shadcn Dialog)
2. Upload an MP3/WAV instrumental
3. Transform → basic-pitch + music21 produces MIDI + MusicXML per stem
4. Download the MIDI package (ZIP of `.mid` + `.musicxml` + guide)
5. Configure local Ollama (Base URL + model) in "AI Settings"
6. Generate rap lyrics in the chosen style
7. Export lyrics as txt

## Tech stack
- Frontend: React, Tailwind, shadcn/ui, lucide-react
- Backend: FastAPI, Motor (async MongoDB)
- Audio: librosa, basic-pitch, pretty_midi, music21, soundfile, scipy
- LLM: **Local Ollama** via REST (`/api/tags` + `/api/generate`)
- LLM: **Local Ollama** (emergentintegrations fully removed)

## What's implemented
- 2025-xx: Base app (MP3 upload, project CRUD, lyric generation)
- 2025-xx: Advanced audio → MIDI/MusicXML pipeline (basic-pitch + music21)
- 2025-xx: Download Complete MIDI Package ZIP endpoint
- **2026-02-19: Switched lyric generation to local Ollama**
  - Added `GET /api/ollama/config` and `POST /api/ollama/test` endpoints
  - Added `ollama_base_url` + `ollama_model` fields to `LyricsRequest`
  - New "AI Settings" tab in Studio with Base URL input, "Test Connection",
    and a Model dropdown populated from `/api/tags`
  - Settings persist in localStorage (key: `ollamaSettings`)
  - Inline "Active AI" indicator in the Generate Lyrics tab
  - Replaced `window.prompt` with a shadcn Dialog for project creation
  - Added data-testids to key interactive elements

## Key endpoints
- `POST /api/projects` — create
- `GET /api/projects` / `GET /api/projects/{id}` — list/get
- `POST /api/projects/{id}/upload` — upload audio
- `POST /api/projects/{id}/transform` — run MIDI pipeline
- `GET /api/projects/{id}/download-stems` — ZIP download
- `POST /api/projects/{id}/generate-lyrics` — lyrics via Ollama
- `GET /api/projects/{id}/download-lyrics` — txt download
- `POST /api/ollama/test` — {base_url} → {connected, models[]}
- `GET /api/ollama/config` — server defaults
- `POST/GET/DELETE /api/user-styles[/id]` — custom style CRUD

## Roadmap
### P0 (done)
- [x] Upload MP3 → MIDI stems + MusicXML ZIP
- [x] Rap lyrics via local Ollama with model picker

### P1 (next)
- [ ] "Learn my style" — let users upload audio/text samples; extract flow metrics
      (rhyme density, syllable cadence) and feed into the lyrics prompt
- [ ] Queue heavy transform as a background job (asyncio.to_thread or Celery) to
      avoid blocking the event loop / ingress timeouts on large files
- [ ] Refactor `server.py` into `routers/` + `services/` modules (file is ~1000 lines)

### P2 (backlog)
- [ ] Better stem separation (Demucs / Spleeter) for truer instrument isolation
- [ ] User authentication (JWT)
- [ ] Validate upload by magic bytes, not just MIME header
- [ ] Persist Ollama settings server-side (per user) once auth lands
- [ ] Disable "Export MIDI Package" header button until transform completes (currently
      disabled by prop check but testing agent flagged UX — consider hiding entirely)

## Known notes
- basic-pitch prints harmless warnings about Coremltools / tflite-runtime / onnxruntime — ignore.
- Pod was previously OOM-killed on large MP3s; current box is sized up but large files still risky.
- Ollama must be reachable from the backend. In the cloud preview, users must expose their
  local Ollama via a tunnel (ngrok/cloudflared) and paste the public URL into AI Settings.

## Test credentials
None — no auth yet. See `/app/memory/test_credentials.md`.
