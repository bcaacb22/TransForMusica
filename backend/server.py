from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone
import shutil
import asyncio
import httpx
import json
import time

# Initialize basic logging early so import-time warnings go to the console
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
_logger = logging.getLogger(__name__)

# Optional heavy imports (audio/ML). If missing, set flags and gracefully degrade.
HAS_NUMPY = HAS_LIBROSA = HAS_SOUNDFILE = HAS_SCIPY = HAS_BASICPITCH = HAS_MUSIC21 = HAS_PRETTYMIDI = HAS_MIDO = False
try:
    import numpy as np
    HAS_NUMPY = True
except Exception as e:
    _logger.warning(f"numpy not available: {e}")

try:
    import librosa
    HAS_LIBROSA = True
except Exception as e:
    _logger.warning(f"librosa not available: {e}")

try:
    import soundfile as sf
    HAS_SOUNDFILE = True
except Exception as e:
    _logger.warning(f"soundfile not available: {e}")

try:
    from scipy import signal
    HAS_SCIPY = True
except Exception as e:
    _logger.warning(f"scipy.signal not available: {e}")

try:
    import basic_pitch
    from basic_pitch.inference import predict
    HAS_BASICPITCH = True
except Exception as e:
    _logger.warning(f"basic_pitch not available: {e}")

try:
    import music21
    HAS_MUSIC21 = True
except Exception as e:
    _logger.warning(f"music21 not available: {e}")

try:
    import pretty_midi
    HAS_PRETTYMIDI = True
except Exception as e:
    _logger.warning(f"pretty_midi not available: {e}")

try:
    import mido
    HAS_MIDO = True
except Exception as e:
    _logger.warning(f"mido not available: {e}")

# Style engine (Learned Style)
from style_engine import (
    heuristic_fingerprint,
    select_representative_samples,
    build_learned_style_prompt,
)
from task_manager import create_bounded_task
from morph_engine import run_morph_pipeline, MorphPlanError, analyze_audio

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create upload directory
UPLOAD_DIR = Path(__file__).parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Pydantic Models
class StatusCheck(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StatusCheckCreate(BaseModel):
    client_name: str

class Project(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    original_file: Optional[str] = None
    transformed_file: Optional[str] = None
    lyrics: Optional[str] = None
    style: Optional[str] = None
    transformation_complete: Optional[bool] = False
    transformation_type: Optional[str] = None
    stems_directory: Optional[str] = None
    midi_files: Optional[List[str]] = Field(default_factory=list)
    musicxml_files: Optional[List[str]] = Field(default_factory=list)
    main_midi: Optional[str] = None
    transcription_file: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda:datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ProjectCreate(BaseModel):
    name: str

class UserStyle(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    sample_lyrics: str = ""
    text_samples: List[str] = Field(default_factory=list)
    audio_sample_transcripts: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class UserStyleCreate(BaseModel):
    name: str
    description: str
    sample_lyrics: str = ""

class UserStyleSampleAdd(BaseModel):
    text: str

class LyricsRequest(BaseModel):
    style: str  # preset key (trap/boom_bap/...) or 'defined' or 'learned' or 'blend'
    structure_mode: Optional[str] = None  # 'placeholder' = keep original bar/rhyme structure, 'fresh' = new structure
    custom_prompt: Optional[str] = None
    user_style_id: Optional[str] = None  # when style == 'defined' or 'blend'
    ollama_base_url: Optional[str] = None
    ollama_model: Optional[str] = None
    llm_api_key: Optional[str] = None  # only needed for hosted OpenAI-compatible providers
    learned_bias: Optional[float] = 0.5  # 0 = heuristic, 1 = LLM-theme
    blend_weight: Optional[float] = 0.5  # 0 = learned only, 1 = defined only (blend mode)
    use_llm_theme: Optional[bool] = True  # if True and learned, run Ollama theme pass

class LyricsResponse(BaseModel):
    lyrics: str
    style: str

class ProfileCorpusItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source: str  # 'generated' | 'text_upload' | 'audio_upload' | 'manual'
    text: str
    title: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Profile(BaseModel):
    id: str = Field(default="default")  # single global profile (no auth yet)
    corpus: List[ProfileCorpusItem] = Field(default_factory=list)
    fingerprint: Optional[Dict[str, Any]] = None
    fingerprint_bias: float = 0.5
    fingerprint_updated_at: Optional[datetime] = None
    llm_theme_summary: Optional[str] = None

class ProfileCorpusAdd(BaseModel):
    text: str
    title: Optional[str] = None
    source: str = "manual"

class FingerprintComputeRequest(BaseModel):
    use_llm_theme: bool = True
    ollama_base_url: Optional[str] = None
    ollama_model: Optional[str] = None
    llm_api_key: Optional[str] = None
    bias: Optional[float] = None

class TranscribeResponse(BaseModel):
    text: str
    language: Optional[str] = None
    duration_seconds: Optional[float] = None

class OllamaTestRequest(BaseModel):
    base_url: str
    api_key: Optional[str] = None

class OllamaModelInfo(BaseModel):
    name: str
    size: Optional[int] = 0
    parameter_size: Optional[str] = ""
    quantization_level: Optional[str] = ""

VOICE_CLONE_URL = os.environ.get("VOICE_CLONE_URL", "").rstrip("/")

# Shazam API v2 — Gateway 01 music recognition (replaces AuDD.io)
SHAZAM_API_KEY = os.environ.get("SHAZAM_API_KEY", "")
SHAZAM_BASE_URL = os.environ.get("SHAZAM_BASE_URL", "https://shazam-api.com").rstrip("/")
# Poll budget for a recognition: submit returns a uuid, results arrive async.
SHAZAM_POLL_INTERVAL_S = 2.5
SHAZAM_POLL_TIMEOUT_S = 120.0

# AcoustID (Chromaprint) — second recognition engine
ACOUSTID_API_KEY = os.environ.get("ACOUSTID_API_KEY", "")
FPCALC_PATH = os.environ.get("FPCALC", str(ROOT_DIR / "fpcalc.exe"))

# AudioTag.info — third recognition engine
AUDIOTAG_API_KEY = os.environ.get("AUDIOTAG_API_KEY", "")
AUDIOTAG_URL = "https://audiotag.info/api"

# Default Ollama config (can be overridden per-request or via env)
DEFAULT_LLM_BASE_URL = os.environ.get('LLM_BASE_URL', os.environ.get('OLLAMA_BASE_URL', 'http://localhost:1234'))
DEFAULT_LLM_MODEL = os.environ.get('LLM_MODEL', os.environ.get('OLLAMA_MODEL', ''))
DEFAULT_OLLAMA_BASE_URL = DEFAULT_LLM_BASE_URL
DEFAULT_OLLAMA_MODEL = DEFAULT_LLM_MODEL

async def ollama_list_models(base_url: str, api_key: str = "") -> List[Dict[str, Any]]:
    base = base_url.rstrip('/')
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    async with httpx.AsyncClient(timeout=httpx.Timeout(10.0, connect=5.0)) as client:
        resp = await client.get(f"{base}/v1/models", headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return [{"name": m.get("id", "unknown"), "size": 0, "details": {}} for m in data.get("data", [])]

async def ollama_generate(base_url: str, model: str, prompt: str, system: str = "", temperature: float = 0.8, api_key: str = "") -> str:
    base = base_url.rstrip('/')
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    async with httpx.AsyncClient(timeout=httpx.Timeout(900.0, connect=10.0)) as client:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = await client.post(f"{base}/v1/chat/completions", headers=headers, json={
            "model": model, "messages": messages, "temperature": temperature,
            "max_tokens": 2048,
            "stream": False, "enable_thinking": False,
        })
        if resp.status_code != 200:
            raise HTTPException(status_code=resp.status_code, detail=f"LLM error: {resp.text}")
        data = resp.json()
        msg = data["choices"][0]["message"]
        content = msg.get("content", "").strip()
        if not content:
            content = msg.get("reasoning_content", "").strip()
        if not content:
            raise HTTPException(status_code=500, detail="LLM returned empty response")
        return content

# ---------------- Whisper (local, faster-whisper) ----------------
_whisper_model = None
def get_whisper_model():
    """Lazy-load faster-whisper tiny.en on first use."""
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        model_size = os.environ.get('WHISPER_MODEL', 'tiny.en')
        # CPU int8 is small + fast on this container
        _whisper_model = WhisperModel(model_size, device="cpu", compute_type="int8")
        logger.info(f"Loaded Whisper model: {model_size}")
    return _whisper_model

def _remote_transcribe(file_path: str, trim_seconds: int = 0) -> str:
    """Send audio to the Windows Demucs server for GPU Whisper transcription."""
    import requests as _req
    demucs_url = os.environ.get("DEMUCS_URL", "").rstrip("/")
    if not demucs_url:
        return ""
    try:
        with open(file_path, "rb") as f:
            params = {"trim_seconds": trim_seconds} if trim_seconds else {}
            resp = _req.post(
                f"{demucs_url}/transcribe",
                files={"audio": (Path(file_path).name, f)},
                params=params,
                timeout=120,
            )
        resp.raise_for_status()
        return resp.json().get("text", "")
    except Exception:
        return ""


def whisper_transcribe(audio_path: str) -> Dict[str, Any]:
    model = get_whisper_model()
    segments, info = model.transcribe(audio_path, beam_size=1)
    text = " ".join(seg.text.strip() for seg in segments).strip()
    return {
        "text": text,
        "language": getattr(info, 'language', None),
        "duration_seconds": getattr(info, 'duration', None),
    }

# ---------------- Profile helpers ----------------
async def get_or_create_profile() -> Dict[str, Any]:
    profile = await db.profiles.find_one({"id": "default"}, {"_id": 0})
    if not profile:
        profile = Profile().dict()
        profile['fingerprint_updated_at'] = None
        await db.profiles.insert_one(profile.copy())
    return profile

async def add_to_profile_corpus(text: str, source: str = 'generated', title: Optional[str] = None):
    if not text or not text.strip():
        return
    item = ProfileCorpusItem(text=text.strip(), source=source, title=title)
    d = item.dict()
    d['created_at'] = d['created_at'].isoformat()
    await db.profiles.update_one(
        {"id": "default"},
        {"$push": {"corpus": d}, "$setOnInsert": {"id": "default", "fingerprint_bias": 0.5}},
        upsert=True,
    )


# Advanced Music Analysis Functions
def _analyze_file_features(file_path: str) -> dict:
    """Load + analyze one audio file (bpm/key). Runs in a worker thread —
    librosa.load, beat_track and chroma_cqt are all CPU-heavy."""
    y, sr = librosa.load(file_path, sr=None, mono=True, duration=60)
    return analyze_audio(y, sr)


def _save_upload_sync(src, dest: Path):
    """Copy an UploadFile's spooled file to disk. Runs in a worker thread —
    uploads are ~39MB and copyfileobj is blocking."""
    with open(dest, "wb") as buffer:
        shutil.copyfileobj(src, buffer)


def _clean_stem(wav_path: Path) -> None:
    """Normalize peak to -1 dBFS and apply a soft noise gate (-45 dB threshold)
    to remove separation artifacts/bleed from a Demucs stem. In-place."""
    import soundfile as _sf
    data, sr = _sf.read(str(wav_path), dtype="float32", always_2d=True)
    peak = float(np.abs(data).max())
    if peak > 1e-8:
        data = data * (10 ** (-1 / 20)) / peak  # normalize to -1 dBFS
    # Soft noise gate: attenuate samples below -45 dB
    threshold = 10 ** (-45 / 20)
    mask = np.abs(data) < threshold
    data[mask] *= 0.05  # attenuate to 5% instead of hard-zeroing (avoids clicks)
    _sf.write(str(wav_path), data, sr, subtype="PCM_16")

def _encode_mp3(wav_path: Path, mp3_path: Path, bitrate: int = 320):
    """Encode a wav stem to mp3 with lameenc (ships as a demucs dependency)."""
    import soundfile as _sf
    import lameenc
    pcm, sr = _sf.read(str(wav_path), dtype="int16", always_2d=True)
    encoder = lameenc.Encoder()
    encoder.set_bit_rate(bitrate)
    encoder.set_in_sample_rate(sr)
    encoder.set_channels(pcm.shape[1])
    encoder.set_quality(2)
    encoder.silence()
    mp3 = encoder.encode(pcm.tobytes()) + encoder.flush()
    mp3_path.write_bytes(mp3)


def _mix_instrumental(output_dir: Path, out_path: Path):
    """Sum the non-vocal stems into a single instrumental wav (the beat without vocals)."""
    import soundfile as _sf
    tracks, sr = [], None
    for name in ["drums", "bass", "other", "guitar", "piano"]:
        p = output_dir / f"{name}.wav"
        if p.exists():
            data, rate = _sf.read(str(p), dtype="float32", always_2d=True)
            tracks.append(data)
            sr = rate
    if not tracks:
        return None
    frames = max(t.shape[0] for t in tracks)
    mixed = np.zeros((frames, tracks[0].shape[1]), dtype=np.float32)
    for t in tracks:
        mixed[:t.shape[0]] += t
    _sf.write(str(out_path), mixed, sr)
    return out_path


def extract_stems_and_convert_to_midi(audio_path, output_dir, progress_cb=None):
    def prog(stage, pct, detail=""):
        if progress_cb:
            try:
                progress_cb(stage, pct, detail)
            except Exception:
                pass

    try:
        import subprocess, sys
        logger.info(f"Starting audio-to-stems conversion for: {audio_path}")

        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)

        # 1. Full-song MIDI via Basic Pitch
        prog("basic_pitch", 5, "Transcribing full track to MIDI")
        logger.info("Converting full audio to MIDI via Basic Pitch...")
        if not HAS_BASICPITCH:
            raise RuntimeError(
                "basic-pitch is not importable in this environment — "
                "see the basic_pitch import warning at startup"
            )
        model_output, midi_data, note_events = predict(audio_path)
        main_midi_file = output_dir / "full_song.mid"
        midi_data.write(str(main_midi_file))
        logger.info(f"Saved full MIDI: {main_midi_file}")
        prog("demucs", 15, "Neural stem separation starting")

        # 2. Neural stem separation via Demucs (GPU server or local CPU fallback)
        logger.info("Running Demucs stem separation...")
        demucs_url = os.environ.get("DEMUCS_URL", "")
        audio_stem = Path(audio_path).stem
        demucs_stems_dir = output_dir / "_stems"
        demucs_stems_dir.mkdir(exist_ok=True)

        use_local = True
        if demucs_url:
            import requests as _requests
            import zipfile as _zipfile
            import io as _io
            try:
                logger.info(f"Using remote Demucs GPU server: {demucs_url}")
                with open(audio_path, "rb") as af:
                    resp = _requests.post(
                        f"{demucs_url}/separate",
                        files={"audio": (Path(audio_path).name, af)},
                        timeout=300,
                    )
                if resp.status_code != 200:
                    logger.warning(f"Remote Demucs {resp.status_code}: {resp.text[:600]}")
                resp.raise_for_status()
                with _zipfile.ZipFile(_io.BytesIO(resp.content)) as zf:
                    zf.extractall(demucs_stems_dir)
                logger.info("Remote Demucs separation complete")
                use_local = False
            except Exception as e:
                logger.warning(f"Remote Demucs failed ({e}), falling back to local CPU")

        if use_local:
            logger.info("No DEMUCS_URL set — running Demucs locally (CPU)")
            # Unique per-run dir: concurrent runs must never share (and rmtree) one.
            demucs_out = output_dir / f"_demucs_{uuid.uuid4().hex[:8]}"
            # wav out: lossless master; mp3s are encoded from these afterwards.
            result = subprocess.run(
                [sys.executable, "-m", "demucs", "-n", "htdemucs_6s",
                 "--out", str(demucs_out), str(audio_path)],
                capture_output=True, text=True
            )
            if result.returncode != 0:
                raise RuntimeError(f"Demucs failed: {result.stderr[-500:]}")
            src_dir = demucs_out / "htdemucs_6s" / audio_stem
            for f in src_dir.glob("*"):
                shutil.copy2(f, demucs_stems_dir / f.name)
            shutil.rmtree(demucs_out, ignore_errors=True)
            logger.info("Local Demucs separation complete")
        prog("midi", 55, "Stem separation done — converting stems to MIDI")
        stem_names = ["drums", "bass", "vocals", "other", "guitar", "piano"]

        midi_files = []
        musicxml_files = []
        audio_stems = []

        for idx, stem_name in enumerate(stem_names):
            prog("midi", 55 + int(idx * 7.5), f"Converting {stem_name} to MIDI")
            stem_src = None
            for ext in ["wav", "mp3"]:
                candidate = demucs_stems_dir / f"{stem_name}.{ext}"
                if candidate.exists():
                    stem_src = candidate
                    break

            if not stem_src:
                logger.warning(f"Demucs did not produce {stem_name}")
                continue

            # Stem audio masters: wav cleaned (normalize + noise gate), mp3 from it
            stem_wav_path = output_dir / f"{stem_name}.wav"
            if stem_src.suffix == ".wav":
                shutil.copy2(stem_src, stem_wav_path)
                try:
                    _clean_stem(stem_wav_path)
                except Exception as e:
                    logger.warning(f"Stem cleanup failed for {stem_name}: {e}")
            else:
                shutil.copy2(stem_src, output_dir / f"{stem_name}.mp3")
                stem_wav_path = None
            if stem_wav_path:
                try:
                    _encode_mp3(stem_wav_path, output_dir / f"{stem_name}.mp3")
                except Exception as e:
                    logger.warning(f"mp3 encode failed for {stem_name}: {e}")
            audio_stems.append(f"{stem_name}.wav" if stem_wav_path else f"{stem_name}.mp3")
            logger.info(f"Saved audio stem: {stem_name}")

            # Convert stem to MIDI via Basic Pitch
            try:
                _, stem_midi, _ = predict(str(stem_wav_path or (output_dir / f"{stem_name}.mp3")))
                stem_midi_path = output_dir / f"{stem_name}.mid"
                stem_midi.write(str(stem_midi_path))
                midi_files.append(stem_midi_path.name)

                musicxml_path = convert_midi_to_musicxml(stem_midi_path, output_dir, stem_name)
                if musicxml_path:
                    musicxml_files.append(musicxml_path)

                logger.info(f"Stem MIDI + MusicXML done: {stem_name}")
            except Exception as e:
                logger.warning(f"MIDI conversion failed for {stem_name}: {e}")
            prog("midi", 55 + int((idx + 1) * 7.5), f"{stem_name} converted")

        # Instrumental = beat without vocals: mix of the non-vocal stems
        prog("instrumental", 86, "Mixing instrumental (beat without vocals)")
        instrumental_wav = output_dir / "instrumental.wav"
        try:
            if _mix_instrumental(output_dir, instrumental_wav):
                _encode_mp3(instrumental_wav, output_dir / "instrumental.mp3")
                _, inst_midi, _ = predict(str(instrumental_wav))
                inst_midi_path = output_dir / "instrumental.mid"
                inst_midi.write(str(inst_midi_path))
                midi_files.append(inst_midi_path.name)
                inst_xml = convert_midi_to_musicxml(inst_midi_path, output_dir, "instrumental")
                if inst_xml:
                    musicxml_files.append(inst_xml)
                audio_stems.append("instrumental.wav")
                logger.info("Instrumental (no vocals) mix done")
        except Exception as e:
            logger.warning(f"Instrumental mix failed: {e}")

        # Full-arrangement MusicXML
        main_musicxml_path = convert_midi_to_musicxml(main_midi_file, output_dir, "full_arrangement")
        if main_musicxml_path:
            musicxml_files.append(main_musicxml_path)

        # Original-vocal transcription (local faster-whisper) — ships in the DAW package
        prog("transcription", 92, "Transcribing original vocals")
        transcription_file = None
        try:
            tr = whisper_transcribe(str(audio_path))
            text = (tr.get("text") or "").strip()
            if text:
                tr_path = output_dir / "transcription.txt"
                tr_path.write_text(text, encoding="utf-8")
                transcription_file = tr_path.name
                logger.info("Original-vocal transcription saved")
        except Exception as e:
            logger.warning(f"Transcription failed: {e}")

        create_transformation_info(output_dir, midi_files, musicxml_files)
        prog("done", 100, "Packaging complete")

        # Clean up stems temp dir
        shutil.rmtree(demucs_stems_dir, ignore_errors=True)

        logger.info("Stem separation and MIDI conversion complete")
        return {
            "main_midi": main_midi_file.name,
            "stem_midis": midi_files,
            "musicxml_files": musicxml_files,
            "audio_stems": audio_stems,
            "transcription_file": transcription_file,
            "success": True
        }

    except Exception as e:
        logger.error(f"Error in advanced audio conversion: {str(e)}")
        return {"success": False, "error": str(e)}

def create_frequency_based_stems(audio, sr):
    """
    Create different stems using frequency separation
    This simulates instrument separation
    """
    stems = {}
    
    # 1. Bass stem (low frequencies)
    bass_audio = apply_frequency_filter(audio, sr, 0, 200)
    stems["bass"] = bass_audio
    
    # 2. Kick/Sub stem (very low frequencies)
    kick_audio = apply_frequency_filter(audio, sr, 0, 80)
    stems["kick"] = kick_audio
    
    # 3. Mid-range stem (vocals/leads)
    mid_audio = apply_frequency_filter(audio, sr, 200, 2000)
    stems["melody"] = mid_audio
    
    # 4. High-frequency stem (hi-hats, cymbals)
    high_audio = apply_frequency_filter(audio, sr, 2000, sr//2)
    stems["percussion"] = high_audio
    
    # 5. Harmonic content (chord progressions)
    harmonic_audio = extract_harmonic_component(audio)
    stems["harmony"] = harmonic_audio
    
    return stems

def apply_frequency_filter(audio, sr, low_freq, high_freq):
    """Apply bandpass filter to isolate frequency range"""
    try:
        nyquist = sr / 2
        
        if low_freq == 0:
            # Low-pass filter
            high_norm = min(high_freq / nyquist, 0.99)
            b, a = signal.butter(4, high_norm, btype='low')
        elif high_freq >= nyquist:
            # High-pass filter
            low_norm = max(low_freq / nyquist, 0.01)
            b, a = signal.butter(4, low_norm, btype='high')
        else:
            # Bandpass filter
            low_norm = max(low_freq / nyquist, 0.01)
            high_norm = min(high_freq / nyquist, 0.99)
            b, a = signal.butter(4, [low_norm, high_norm], btype='band')
        
        filtered = signal.filtfilt(b, a, audio)
        return filtered
        
    except Exception as e:
        logger.warning(f"Filter error: {str(e)}, returning original audio")
        return audio * 0.1  # Return quieter version as fallback

def extract_harmonic_component(audio):
    """Extract harmonic components using librosa"""
    try:
        # Use harmonic-percussive separation
        harmonic, _ = librosa.effects.hpss(audio)
        return harmonic
    except Exception as e:
        logger.warning(f"Harmonic extraction error: {str(e)}")
        return audio * 0.5

def convert_midi_to_musicxml(midi_path, output_dir, name):
    """Convert MIDI to MusicXML using music21"""
    try:
        # Load MIDI with music21
        midi_stream = music21.converter.parse(str(midi_path))
        
        # Enhance the score for better notation
        midi_stream = enhance_musical_score(midi_stream)
        
        # Export to MusicXML
        musicxml_path = output_dir / f"{name}.musicxml"
        midi_stream.write('musicxml', fp=str(musicxml_path))
        
        logger.info(f"Created MusicXML: {musicxml_path}")
        return musicxml_path.name
        
    except Exception as e:
        logger.error(f"Error converting MIDI to MusicXML: {str(e)}")
        return None

def enhance_musical_score(stream):
    """Enhance the musical score with better formatting"""
    try:
        # Add time signature if missing
        if not stream.getElementsByClass(music21.meter.TimeSignature):
            stream.insert(0, music21.meter.TimeSignature('4/4'))
        
        # Add key signature if missing  
        if not stream.getElementsByClass(music21.key.KeySignature):
            stream.insert(0, music21.key.Key('C', 'major'))
        
        # Quantize notes to reasonable durations
        stream = stream.quantize()
        
        return stream
        
    except Exception as e:
        logger.warning(f"Score enhancement error: {str(e)}")
        return stream

def create_transformation_info(output_dir, midi_files, musicxml_files):
    """Create info file about the transformation"""
    info_content = f"""# Audio-to-MIDI Transformation Results

## Original Composition Breakdown

This transformation has converted your uploaded instrumental into:

### MIDI Files (Ready for DAW Import):
{chr(10).join(f"- {file}" for file in midi_files)}

### MusicXML Files (Musical Notation):
{chr(10).join(f"- {file}" for file in musicxml_files)}

### How to Use These Files:

1. **MIDI Files (.mid)**:
   - Import into any DAW (Logic Pro, Ableton, FL Studio, etc.)
   - Change instruments on each track to create completely new sounds
   - Modify tempo, key, and arrangements
   - Layer with your own recordings

2. **MusicXML Files (.musicxml)**:
   - Open in notation software (Sibelius, Finale, MuseScore)
   - Edit the musical notation directly
   - Print as sheet music
   - Share with musicians for live performance

### Legal Benefits:
- **Original Composition**: These MIDI files represent the musical structure, not the original audio
- **Transformative Use**: You can create entirely new recordings using these arrangements
- **Copyright Ready**: Your new compositions using these files are original works
- **Commercial Use**: Safe for commercial release and copyright registration

### Recommended Workflow:
1. Import MIDI files into your DAW
2. Assign different instruments to each track
3. Adjust velocities, timing, and expression
4. Add your own elements (vocals, additional instruments)
5. Mix and master as your original composition

Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    info_path = output_dir / "transformation_guide.txt"
    with open(info_path, 'w', encoding='utf-8') as f:
        f.write(info_content)
    
    logger.info(f"Created transformation guide: {info_path}")

# Routes
@api_router.get("/")
async def root():
    return {"message": "Beat Maker API Ready"}

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.dict()
    status_obj = StatusCheck(**status_dict)
    await db.status_checks.insert_one(status_obj.dict())
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    status_checks = await db.status_checks.find().to_list(1000)
    return [StatusCheck(**status_check) for status_check in status_checks]

# Project Management
@api_router.post("/projects", response_model=Project)
async def create_project(project: ProjectCreate):
    project_obj = Project(**project.dict())
    project_dict = project_obj.dict()
    project_dict['created_at'] = project_dict['created_at'].isoformat()
    project_dict['updated_at'] = project_dict['updated_at'].isoformat()
    await db.projects.insert_one(project_dict)
    return project_obj

@api_router.get("/projects", response_model=List[Project])
async def get_projects():
    projects = await db.projects.find().to_list(1000)
    for project in projects:
        if isinstance(project.get('created_at'), str):
            project['created_at'] = datetime.fromisoformat(project['created_at'])
        if isinstance(project.get('updated_at'), str):
            project['updated_at'] = datetime.fromisoformat(project['updated_at'])
    return [Project(**project) for project in projects]

@api_router.get("/projects/{project_id}", response_model=Project)
async def get_project(project_id: str):
    project = await db.projects.find_one({"id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if isinstance(project.get('created_at'), str):
        project['created_at'] = datetime.fromisoformat(project['created_at'])
    if isinstance(project.get('updated_at'), str):
        project['updated_at'] = datetime.fromisoformat(project['updated_at'])
    
    return Project(**project)

# File Upload
@api_router.post("/projects/{project_id}/upload")
async def upload_file(project_id: str, file: UploadFile = File(...)):
    # Check if project exists
    project = await db.projects.find_one({"id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Validate file type
    allowed_types = ['audio/mpeg', 'audio/wav', 'audio/mp3', 'audio/x-wav']
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload audio files only.")
    
    # Save file
    file_extension = Path(file.filename).suffix
    filename = f"{project_id}_original{file_extension}"
    file_path = UPLOAD_DIR / filename
    
    await asyncio.to_thread(_save_upload_sync, file.file, file_path)
    
    # Update project
    await db.projects.update_one(
        {"id": project_id},
        {
            "$set": {
                "original_file": filename,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }
        }
    )
    
    return {"message": "File uploaded successfully", "filename": filename}


# Legal Scan — Shazam API v2 recognition
async def _shazam_recognize(file_path: Path) -> dict:
    """Submit audio to Shazam v2 /recognize and poll /results until terminal.

    Returns {'status': 'success'|'no_matches'|'failed', 'results': [...],
    'code': str|None, 'error': str|None}. Raises on HTTP/transport errors so the
    caller maps them to the UNKNOWN risk path.
    """
    headers = {"Authorization": f"Bearer {SHAZAM_API_KEY}"}
    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
        with open(file_path, "rb") as f:
            resp = await client.post(
                f"{SHAZAM_BASE_URL}/api/v2/recognize",
                headers=headers,
                files={"file": (file_path.name, f, "audio/mpeg")},
                data={"metadata": json.dumps({"project": "transformusic"})},
            )
        resp.raise_for_status()
        submitted = resp.json()
        results_url = submitted.get("resultsUrl") or f"/api/v2/results/{submitted['uuid']}"

        deadline = time.monotonic() + SHAZAM_POLL_TIMEOUT_S
        while time.monotonic() < deadline:
            await asyncio.sleep(SHAZAM_POLL_INTERVAL_S)
            r = await client.get(f"{SHAZAM_BASE_URL}{results_url}", headers=headers)
            r.raise_for_status()
            data = r.json()
            status = data.get("status")
            if status == "processing":
                continue
            if status == "success":
                return {"status": "success", "results": data.get("results", []),
                        "code": None, "error": None}
            if status == "no_matches":
                return {"status": "no_matches", "results": [], "code": None, "error": None}
            return {"status": "failed", "results": [],
                    "code": data.get("code"), "error": data.get("error")}
        return {"status": "failed", "results": [], "code": "TIMEOUT",
                "error": f"Recognition still processing after {int(SHAZAM_POLL_TIMEOUT_S)}s"}


def _acoustid_recognize_sync(file_path: Path) -> dict:
    """Fingerprint with fpcalc + query AcoustID. Returns the same shape as
    _shazam_recognize: {'status': 'success'|'no_matches'|'failed', ...}."""
    import acoustid
    os.environ["FPCALC"] = FPCALC_PATH
    duration, fingerprint = acoustid.fingerprint_file(str(file_path))
    results = acoustid.lookup(ACOUSTID_API_KEY, fingerprint, duration)
    if results.get("status") != "ok":
        return {"status": "failed", "results": [], "code": "API_ERROR",
                "error": str(results.get("error", results))}
    matches = results.get("results", [])
    if not matches:
        return {"status": "no_matches", "results": [], "code": None, "error": None}
    # Take the best-scoring recording
    best = max(matches, key=lambda r: r.get("score", 0))
    recordings = best.get("recordings", [])
    if not recordings:
        return {"status": "no_matches", "results": [], "code": None, "error": None}
    rec = recordings[0]
    artists = ", ".join(a.get("name", "") for a in rec.get("artists", []))
    return {"status": "success", "results": [{
        "title": rec.get("title"),
        "artist": artists or None,
        "album": None,
        "releaseDate": None,
        "timecode": None,
        "isrc": rec.get("isrcs", [None])[0] if rec.get("isrcs") else None,
        "genre": None,
        "artwork": None,
        "links": {},
    }], "code": None, "error": None}


def _audiotag_recognize_sync(file_path: Path) -> dict:
    """Submit audio to AudioTag.info identify + poll get_result.
    Returns the same shape as _shazam_recognize."""
    import requests as _rq
    import time as _t

    with open(file_path, "rb") as f:
        resp = _rq.post(AUDIOTAG_URL,
                        data={"apikey": AUDIOTAG_API_KEY, "action": "identify"},
                        files={"file": (file_path.name, f, "audio/wav")},
                        timeout=60)
    resp.raise_for_status()
    data = resp.json()
    if not data.get("success"):
        return {"status": "failed", "results": [], "code": "API_ERROR",
                "error": data.get("error", str(data))}
    token = data.get("token")
    if not token:
        return {"status": "failed", "results": [], "code": "NO_TOKEN",
                "error": "No token returned"}

    # Poll for result (tokens valid 5 min; results usually ready in <15s)
    deadline = _t.monotonic() + 90
    while _t.monotonic() < deadline:
        _t.sleep(3)
        r = _rq.post(AUDIOTAG_URL,
                     data={"apikey": AUDIOTAG_API_KEY, "action": "get_result", "token": token},
                     timeout=30)
        r.raise_for_status()
        rd = r.json()
        result = rd.get("result")
        if result == "wait":
            continue
        if result == "found":
            d = rd.get("data", {})
            return {"status": "success", "results": [{
                "title": d.get("title"),
                "artist": d.get("artist"),
                "album": d.get("album"),
                "releaseDate": None,
                "timecode": None,
                "isrc": None,
                "genre": None,
                "artwork": None,
                "links": {},
            }], "code": None, "error": None}
        # "not found"
        return {"status": "no_matches", "results": [], "code": None, "error": None}
    return {"status": "failed", "results": [], "code": "TIMEOUT",
            "error": "AudioTag result not ready after 90s"}


@api_router.post("/projects/{project_id}/legal-scan")
async def legal_scan(project_id: str):
    project = await db.projects.find_one({"id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    original_file = project.get("original_file")
    if not original_file:
        raise HTTPException(status_code=400, detail="No file uploaded for this project")

    file_path = UPLOAD_DIR / original_file
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found on disk")

    try:
        # Run BOTH recognition engines — results shown side by side in the report.
        scan_error = None
        shazam_result = None
        acoustid_result = None
        audiotag_result = None
        shazam_ran_clean = False
        acoustid_ran_clean = False
        audiotag_ran_clean = False

        if SHAZAM_API_KEY:
            try:
                rec = await _shazam_recognize(file_path)
                if rec["status"] == "success" and rec["results"]:
                    r = rec["results"][0]
                    links = r.get("links") or {}
                    shazam_result = {
                        "source": "Shazam API v2",
                        "matchedSource": f"{r.get('title')} — {r.get('artist')}" if r.get('artist') else r.get('title'),
                        "isrc": r.get("isrc"),
                        "label": None,
                        "releaseDate": r.get("releaseDate"),
                        "genre": r.get("genre"),
                        "album": r.get("album"),
                        "timecode": r.get("timecode"),
                        "spotifyUrl": links.get("spotify"),
                        "appleMusicUrl": links.get("appleMusic"),
                        "albumArt": r.get("artwork"),
                        "songLink": links.get("shazam"),
                    }
                    matched_by = "Shazam API v2"
                    shazam_ran_clean = True
                elif rec["status"] == "failed":
                    scan_error = f"Shazam {rec['code']}: {rec['error']}"
                elif rec["status"] == "no_matches":
                    shazam_ran_clean = True
            except Exception as e:
                scan_error = str(e)
        else:
            scan_error = "no SHAZAM_API_KEY configured"

        if ACOUSTID_API_KEY:
            try:
                rec2 = await asyncio.to_thread(_acoustid_recognize_sync, file_path)
                if rec2["status"] == "success" and rec2["results"]:
                    r = rec2["results"][0]
                    acoustid_result = {
                        "source": "AcoustID (Chromaprint)",
                        "matchedSource": f"{r.get('title')} — {r.get('artist')}" if r.get('artist') else r.get('title'),
                        "isrc": r.get("isrc"),
                        "label": None,
                        "releaseDate": None,
                        "genre": None,
                        "album": None,
                        "timecode": None,
                        "spotifyUrl": None,
                        "appleMusicUrl": None,
                        "albumArt": None,
                        "songLink": None,
                    }
                    acoustid_ran_clean = True
                elif rec2["status"] == "no_matches":
                    acoustid_ran_clean = True
            except Exception:
                pass  # AcoustID failure is silent

        if AUDIOTAG_API_KEY:
            try:
                rec3 = await asyncio.to_thread(_audiotag_recognize_sync, file_path)
                if rec3["status"] == "success" and rec3["results"]:
                    r = rec3["results"][0]
                    audiotag_result = {
                        "source": "AudioTag.info",
                        "matchedSource": f"{r.get('title')} — {r.get('artist')}" if r.get('artist') else r.get('title'),
                        "isrc": r.get("isrc"),
                        "label": None,
                        "releaseDate": None,
                        "genre": None,
                        "album": r.get("album"),
                        "timecode": None,
                        "spotifyUrl": None,
                        "appleMusicUrl": None,
                        "albumArt": None,
                        "songLink": None,
                    }
                    audiotag_ran_clean = True
                elif rec3["status"] == "no_matches":
                    audiotag_ran_clean = True
            except Exception:
                pass  # AudioTag failure is silent

        # Primary match = whichever engine found something (Shazam preferred)
        primary = shazam_result or acoustid_result or audiotag_result
        match_title = None
        match_artist = match_album = match_label = None
        match_release_date = match_timecode = match_isrc = match_genre = None
        match_spotify_url = match_apple_music_url = match_album_art = match_song_link = None
        matched_by = None
        if primary:
            match_title = primary["matchedSource"]
            match_isrc = primary.get("isrc")
            match_release_date = primary.get("releaseDate")
            match_timecode = primary.get("timecode")
            match_genre = primary.get("genre")
            match_album = primary.get("album")
            match_spotify_url = primary.get("spotifyUrl")
            match_apple_music_url = primary.get("appleMusicUrl")
            match_album_art = primary.get("albumArt")
            match_song_link = primary.get("songLink")
            matched_by = primary["source"]
            if primary.get("matchedSource") and " — " in primary["matchedSource"]:
                match_title, match_artist = primary["matchedSource"].split(" — ", 1)

        # Get duration via ffprobe
        duration = None
        try:
            proc = await asyncio.create_subprocess_exec(
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", str(file_path),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=15)
            duration = int(float(stdout.decode().strip()))
        except Exception:
            pass

        # Extract audio features with librosa — the whole analysis runs in a
        # worker thread (beat_track + chroma_cqt are CPU-heavy; only load was
        # offloaded before, leaving feature extraction on the event loop).
        try:
            analysis = await asyncio.to_thread(_analyze_file_features, str(file_path))
            bpm = analysis["bpm"]
            key = analysis["key_name"]
        except Exception:
            bpm = None
            key = None

        # Whisper transcription — offloaded to Windows GPU via Demucs server
        lyrical_match = None
        transcribed = ""
        try:
            transcribed = await asyncio.to_thread(_remote_transcribe, str(file_path), 60)
        except Exception:
            pass

        # Lyrical match via lyrics.ovh — only when recognition identified the track
        if match_title and match_artist and transcribed:
            try:
                import urllib.parse
                lyrics_url = f"https://api.lyrics.ovh/v1/{urllib.parse.quote(match_artist)}/{urllib.parse.quote(match_title)}"
                async with httpx.AsyncClient(timeout=10) as lc:
                    lr = await lc.get(lyrics_url)
                    if lr.status_code == 200:
                        known_lyrics = lr.json().get("lyrics", "")
                        if known_lyrics:
                            from difflib import SequenceMatcher
                            ratio = SequenceMatcher(None, transcribed.lower(), known_lyrics.lower()).ratio()
                            lyrical_match = round(ratio * 100, 1)
            except Exception:
                pass

        # Determine violation risk based on scan outcome.
        # If at least one engine ran and returned a clean "no match", that's
        # a definitive NONE — not "LOOKUP UNAVAILABLE". UNKNOWN only when
        # every engine errored out.
        any_engine_ran_clean = shazam_ran_clean or acoustid_ran_clean or audiotag_ran_clean
        if not SHAZAM_API_KEY and not ACOUSTID_API_KEY and not AUDIOTAG_API_KEY:
            violation_risk = "UNAVAILABLE"
            matched_source = "SCAN UNAVAILABLE — no recognition API key configured"
        elif match_title:
            violation_risk = "HIGH"
            matched_source = f"{match_title} — {match_artist}" if match_artist else match_title
        elif any_engine_ran_clean:
            violation_risk = "NONE"
            matched_source = "NO MATCH FOUND"
        elif scan_error:
            violation_risk = "UNKNOWN"
            matched_source = "LOOKUP UNAVAILABLE"
        else:
            violation_risk = "NONE"
            matched_source = "NO MATCH FOUND"

        result = {
            "similarityScore": 100 if match_title else 0,
            "matchedSource": matched_source,
            "matchedBy": matched_by,
            "audioFingerprint": match_isrc or "NOT REGISTERED",
            "lyricalMatch": lyrical_match,
            "violationRisk": violation_risk,
            "bpm": bpm,
            "key": key,
            "duration": duration,
            "isrc": match_isrc,
            "label": match_label,
            "releaseDate": match_release_date,
            "genre": match_genre,
            "spotifyUrl": match_spotify_url,
            "appleMusicUrl": match_apple_music_url,
            "albumArt": match_album_art,
            "timecode": match_timecode,
            "songLink": match_song_link,
            "album": match_album,
            "original_transcription": transcribed,
            "scanError": scan_error,
            "shazamResult": shazam_result,
            "acoustidResult": acoustid_result,
            "audiotagResult": audiotag_result,
        }

        update_fields = {"legal_scan": result, "updated_at": datetime.now(timezone.utc).isoformat()}
        if transcribed:
            update_fields["original_transcription"] = transcribed
        await db.projects.update_one(
            {"id": project_id},
            {"$set": update_fields}
        )

        return result

    except HTTPException:
        raise
    except Exception as e:
        # Top-level safety net: never return a 500 due to scan issues
        logger.error(f"Unexpected error in legal_scan for project {project_id}: {e}")
        return {
            "similarityScore": 0,
            "matchedSource": "SCAN FAILED",
            "audioFingerprint": "NOT REGISTERED",
            "lyricalMatch": None,
            "violationRisk": "UNKNOWN",
            "bpm": None,
            "key": None,
            "duration": None,
            "isrc": None,
            "label": None,
            "releaseDate": None,
            "genre": None,
            "spotifyUrl": None,
            "appleMusicUrl": None,
            "albumArt": None,
            "timecode": None,
            "songLink": None,
            "original_transcription": "",
            "scanError": f"Unexpected error: {str(e)}",
        }


# Beat Transformation (Advanced Audio-to-MIDI Conversion)
# In-memory progress for in-flight transforms (survives only while the task runs).
# transform-status falls back to this while a task is live, and to a stale-recovery
# failure when the DB says "processing" but no task is actually running.
_TRANSFORM_PROGRESS: Dict[str, Dict[str, Any]] = {}


def _set_progress(project_id: str, stage: str, pct: int, detail: str = ""):
    _TRANSFORM_PROGRESS[project_id] = {
        "stage": stage, "percent": int(pct), "detail": detail,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


async def _run_transform(project_id: str, original_path: str):
    """Background task: runs Demucs + Basic Pitch, writes results to DB."""
    transform_dir = UPLOAD_DIR / f"{project_id}_stems"
    transform_dir.mkdir(exist_ok=True)
    _set_progress(project_id, "start", 0, "Starting")
    try:
        loop = asyncio.get_event_loop()
        transformation_result = await loop.run_in_executor(
            None, extract_stems_and_convert_to_midi, original_path, str(transform_dir),
            lambda stage, pct, detail="": _set_progress(project_id, stage, pct, detail),
        )
        if not transformation_result.get("success"):
            raise RuntimeError(transformation_result.get("error", "Unknown error"))
        await db.projects.update_one(
            {"id": project_id},
            {"$set": {
                "stems_directory": f"{project_id}_stems",
                "midi_files": transformation_result.get("stem_midis", []),
                "musicxml_files": transformation_result.get("musicxml_files", []),
                "audio_stems": transformation_result.get("audio_stems", []),
                "main_midi": transformation_result.get("main_midi"),
                "transcription_file": transformation_result.get("transcription_file"),
                "transformation_type": "advanced_stems_midi",
                "transformation_complete": True,
                "transform_status": "complete",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }}
        )
        logger.info(f"Transformation complete for {project_id}")
    except Exception as e:
        logger.error(f"Transformation failed for {project_id}: {e}")
        await db.projects.update_one(
            {"id": project_id},
            {"$set": {"transform_status": "failed", "transform_error": str(e),
                      "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
    finally:
        _TRANSFORM_PROGRESS.pop(project_id, None)


@api_router.post("/projects/{project_id}/transform")
async def transform_beat(project_id: str):
    project = await db.projects.find_one({"id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.get('original_file'):
        raise HTTPException(status_code=400, detail="No original file uploaded")
    original_path = UPLOAD_DIR / project['original_file']
    if not original_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found on disk")

    # Atomic claim: only the request that flips status -> "processing" starts the
    # pipeline. A second near-simultaneous request (React StrictMode double-mount)
    # matches 0 documents and returns early instead of starting a duplicate run.
    claimed = await db.projects.update_one(
        {"id": project_id, "transform_status": {"$ne": "processing"}},
        {"$set": {"transform_status": "processing", "transform_error": None,
                  "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    if claimed.matched_count == 0:
        return {"status": "processing", "project_id": project_id}

    try:
        await create_bounded_task(_run_transform(project_id, str(original_path)), name=f"transform-{project_id}")
    except Exception as e:
        logger.error(f"Failed to start transform task for {project_id}: {e}")
        await db.projects.update_one(
            {"id": project_id},
            {"$set": {"transform_status": "failed", "transform_error": str(e),
                      "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        raise HTTPException(status_code=500, detail={"error": str(e), "message": "Failed to start transform task"})
    return {"status": "processing", "project_id": project_id}


@api_router.get("/projects/{project_id}/transform-status")
async def transform_status(project_id: str):
    project = await db.projects.find_one({"id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    status = project.get("transform_status", "pending")
    if status == "complete":
        # bpm/key come from the GW01 legal scan of the same source file — real
        # detected values instead of frontend mocks (None if GW01 never ran).
        legal = project.get("legal_scan") or {}
        return {
            "status": "complete",
            "success": True,
            "stem_midis": project.get("midi_files", []),
            "midi_files": project.get("midi_files", []),
            "musicxml_files": project.get("musicxml_files", []),
            "audio_stems": project.get("audio_stems", []),
            "main_midi": project.get("main_midi"),
            "bpm": legal.get("bpm"),
            "key": legal.get("key"),
        }
    if status == "failed":
        # 200, not 500: a failed transform is a valid status answer. A 500 here
        # makes the frontend poller treat the failure as transient and retry forever.
        error_msg = project.get("transform_error", "Unknown error")
        return {"status": "failed", "success": False, "error": error_msg}
    if status == "processing":
        prog = _TRANSFORM_PROGRESS.get(project_id)
        if prog:
            return {"status": "processing", "progress": prog}
        # DB says processing but no task is running in this process — the backend
        # restarted (or the task died) mid-run. Recover to a failed state so the
        # UI stops polling forever and the user can retry.
        await db.projects.update_one(
            {"id": project_id},
            {"$set": {"transform_status": "failed",
                      "transform_error": "Transform was interrupted (server restarted). Please run it again.",
                      "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        return {"status": "failed", "success": False,
                "error": "Transform was interrupted (server restarted). Please run it again."}
    return {"status": status}

# ── Gateway 03: Morph Engine ─────────────────────────────────────────────
# Deterministic DSP morph of the GW02 instrumental stems (see morph_engine.py).
# Progress + status + atomic-claim pattern mirrors the transform pipeline above.

class MorphRequest(BaseModel):
    similarity_target: Optional[int] = 35
    key_target: Optional[str] = None
    bpm_target: Optional[float] = None


# In-memory progress for in-flight morphs (separate dict from transforms so a
# morph never masks a transform's progress).
_MORPH_PROGRESS: Dict[str, Dict[str, Any]] = {}


def _set_morph_progress(project_id: str, stage: str, pct: int, detail: str = ""):
    _MORPH_PROGRESS[project_id] = {
        "stage": stage, "percent": int(pct), "detail": detail,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


async def _run_morph(project_id: str, stems_dir: str, morph_dir: str, params: dict):
    """Background task: runs the morph pipeline in a worker thread, writes results to DB."""
    _set_morph_progress(project_id, "start", 0, "Starting morph")
    try:
        loop = asyncio.get_event_loop()
        morph_result = await loop.run_in_executor(
            None, run_morph_pipeline, stems_dir, morph_dir, params,
            lambda stage, pct, detail="": _set_morph_progress(project_id, stage, pct, detail),
        )
        if not morph_result.get("success"):
            raise RuntimeError(morph_result.get("error", "Unknown morph error"))
        await db.projects.update_one(
            {"id": project_id},
            {"$set": {
                "morph_status": "complete",
                "morph_error": None,
                "morph_directory": f"{project_id}_morph",
                "morph_params": params,
                "morph_result": morph_result.get("result", {}),
                "morphed_files": morph_result.get("files", []),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }}
        )
        logger.info(f"Morph complete for {project_id}")
    except Exception as e:
        logger.error(f"Morph failed for {project_id}: {e}")
        await db.projects.update_one(
            {"id": project_id},
            {"$set": {"morph_status": "failed", "morph_error": str(e),
                      "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
    finally:
        _MORPH_PROGRESS.pop(project_id, None)


@api_router.post("/projects/{project_id}/morph")
async def morph_beat(project_id: str, body: MorphRequest = MorphRequest()):
    project = await db.projects.find_one({"id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.get("transform_status") != "complete" or not project.get("stems_directory"):
        raise HTTPException(status_code=400, detail="Run deconstruction (Gateway 02) first")
    if body.similarity_target is not None and not (0 <= body.similarity_target <= 79):
        raise HTTPException(status_code=400, detail="similarity_target must be between 0 and 79")

    stems_dir = UPLOAD_DIR / project["stems_directory"]
    if not stems_dir.exists():
        raise HTTPException(status_code=404, detail="Stems directory not found on disk")
    has_source = (stems_dir / "instrumental.wav").exists() or any(
        (stems_dir / f"{n}.wav").exists() for n in ["drums", "bass", "other"])
    if not has_source:
        raise HTTPException(status_code=404, detail="No instrumental stems found on disk")

    morph_dir = UPLOAD_DIR / f"{project_id}_morph"
    params = {
        "similarity_target": body.similarity_target if body.similarity_target is not None else 35,
        "key_target": body.key_target,
        "bpm_target": body.bpm_target,
    }

    # Atomic claim: only the request that flips status -> "processing" starts the
    # pipeline (StrictMode double-mount safe). Re-morphing a complete project is
    # allowed — the claim only blocks concurrent runs.
    claimed = await db.projects.update_one(
        {"id": project_id, "morph_status": {"$ne": "processing"}},
        {"$set": {"morph_status": "processing", "morph_error": None,
                  "morph_params": params,
                  "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    if claimed.matched_count == 0:
        return {"status": "processing", "project_id": project_id}

    try:
        await create_bounded_task(
            _run_morph(project_id, str(stems_dir), str(morph_dir), params),
            name=f"morph-{project_id}")
    except Exception as e:
        logger.error(f"Failed to start morph task for {project_id}: {e}")
        await db.projects.update_one(
            {"id": project_id},
            {"$set": {"morph_status": "failed", "morph_error": str(e),
                      "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        raise HTTPException(status_code=500, detail={"error": str(e), "message": "Failed to start morph task"})
    return {"status": "processing", "project_id": project_id}


@api_router.get("/projects/{project_id}/morph-status")
async def morph_status(project_id: str):
    project = await db.projects.find_one({"id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    status = project.get("morph_status", "pending")
    if status == "complete":
        # True Isolation: fully rendered from the DB doc — survives refresh.
        return {
            "status": "complete",
            "success": True,
            "morph_params": project.get("morph_params", {}),
            "morph_result": project.get("morph_result", {}),
            "morphed_files": project.get("morphed_files", []),
        }
    if status == "failed":
        # 200, not 500: a failed morph is a valid status answer (same rationale
        # as transform-status — a 500 makes the poller retry forever).
        return {"status": "failed", "success": False,
                "error": project.get("morph_error", "Unknown error")}
    if status == "processing":
        prog = _MORPH_PROGRESS.get(project_id)
        if prog:
            return {"status": "processing", "progress": prog}
        # DB says processing but no task is running in this process — the backend
        # restarted (or the task died) mid-run. Recover to failed.
        await db.projects.update_one(
            {"id": project_id},
            {"$set": {"morph_status": "failed",
                      "morph_error": "Morph was interrupted (server restarted). Please run it again.",
                      "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
        return {"status": "failed", "success": False,
                "error": "Morph was interrupted (server restarted). Please run it again."}
    return {"status": status}


@api_router.get("/projects/{project_id}/morph-preview")
async def morph_preview(project_id: str):
    project = await db.projects.find_one({"id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.get("morph_status") != "complete" or not project.get("morph_directory"):
        raise HTTPException(status_code=404, detail="No morph available — run the morph first")
    morph_dir = UPLOAD_DIR / project["morph_directory"]
    preview_path = None
    for name in ["instrumental.mp3", "instrumental.wav"]:
        cand = morph_dir / name
        if cand.exists():
            preview_path = cand
            break
    if not preview_path:
        raise HTTPException(status_code=404, detail="Morphed instrumental not found on disk")
    media_type = "audio/mpeg" if preview_path.suffix.lower() == ".mp3" else "audio/wav"
    return FileResponse(str(preview_path), media_type=media_type)

# New endpoint to download transformation package
@api_router.get("/projects/{project_id}/download-stems")
async def download_stems_package(project_id: str):
    """Download complete MIDI/MusicXML package as ZIP"""
    project = await db.projects.find_one({"id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if not project.get('stems_directory'):
        raise HTTPException(status_code=404, detail="No stems available. Please transform the beat first.")
    
    stems_dir = UPLOAD_DIR / project['stems_directory']
    if not stems_dir.exists():
        raise HTTPException(status_code=404, detail="Stems directory not found")
    
    # Create ZIP file — structured DAW package
    import zipfile
    zip_filename = f"{project['name']}_DAW_Package.zip"
    zip_path = UPLOAD_DIR / zip_filename

    def _add(zipf, folder: str, names):
        for n in names:
            p = stems_dir / n
            if p.exists():
                zipf.write(p, f"{folder}/{n}" if folder else n)

    try:
        # ZIP build (up to ~180MB of wav/mp3/midi) runs in a worker thread —
        # it was blocking the event loop for seconds.
        def _build_zip():
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                vocal_extra = [project["transcription_file"]] if project.get("transcription_file") else []
                _add(zipf, "Vocal", vocal_extra + [
                    "vocals.mp3", "vocals.wav", "vocals.mid", "vocals.musicxml"])
                _add(zipf, "Instrumental", [
                    "instrumental.mp3", "instrumental.wav", "instrumental.mid", "instrumental.musicxml"])
                _add(zipf, "Full_Arrangement", ["full_song.mid", "full_arrangement.musicxml"])
                for stem in ["drums", "bass", "other", "guitar", "piano"]:
                    _add(zipf, f"Stems/{stem}", [
                        f"{stem}.mp3", f"{stem}.wav", f"{stem}.mid", f"{stem}.musicxml"])
                _add(zipf, "", ["transformation_guide.txt"])

        await asyncio.to_thread(_build_zip)

        return FileResponse(
            zip_path,
            filename=zip_filename,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={zip_filename}"}
        )
        
    except Exception as e:
        logger.error(f"Error creating stems package: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to create stems package")

@api_router.get("/projects/{project_id}/download-beat")
async def download_beat(project_id: str):
    """The cleared beat = the morphed instrumental (GW03), falling back to the
    deconstructed instrumental (GW02), falling back to the original."""
    project = await db.projects.find_one({"id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    beat_path = None
    # Morph output wins when Gateway 03 completed — doctrine: the Cleared Beat
    # IS the morph result; GW04/GW05 consumers automatically get it.
    if project.get("morph_status") == "complete" and project.get("morph_directory"):
        morph_dir = UPLOAD_DIR / project["morph_directory"]
        for name in ["instrumental.mp3", "instrumental.wav"]:
            cand = morph_dir / name
            if cand.exists():
                beat_path = cand
                break
    if not beat_path:
        stems_dir = UPLOAD_DIR / project['stems_directory'] if project.get('stems_directory') else None
        if stems_dir and stems_dir.exists():
            for name in ["instrumental.mp3", "instrumental.wav"]:
                cand = stems_dir / name
                if cand.exists():
                    beat_path = cand
                    break
    if not beat_path:
        beat_file = project.get("transformed_file") or project.get("original_file")
        if not beat_file:
            raise HTTPException(status_code=404, detail="No beat file found for this project")
        beat_path = UPLOAD_DIR / beat_file
    if not beat_path.exists():
        raise HTTPException(status_code=404, detail="Beat file not found on disk")
    media_type = "audio/mpeg" if beat_path.suffix.lower() == ".mp3" else "audio/wav"
    return FileResponse(str(beat_path), media_type=media_type, filename=f"CLEARED_BEAT{beat_path.suffix}")


@api_router.get("/projects/{project_id}/transcription")
async def get_transcription(project_id: str):
    """Return the original-vocal transcription text (Gateway 02)."""
    project = await db.projects.find_one({"id": project_id})
    if not project or not project.get('stems_directory'):
        raise HTTPException(status_code=404, detail="No transcription for this project")
    tr_name = project.get("transcription_file")
    if not tr_name:
        return {"text": ""}
    path = UPLOAD_DIR / project['stems_directory'] / tr_name
    if not path.exists():
        return {"text": ""}
    return {"text": path.read_text(encoding="utf-8")}


@api_router.get("/projects/{project_id}/stem-audio/{stem_name}")
async def stream_stem_audio(project_id: str, stem_name: str):
    """Stream a stem audio file (for in-app playback). stem_name e.g. 'vocals.wav'."""
    project = await db.projects.find_one({"id": project_id})
    if not project or not project.get('stems_directory'):
        raise HTTPException(status_code=404, detail="No stems for this project")
    if stem_name not in {
        f"{s}.{e}" for s in ["drums", "bass", "vocals", "other", "guitar", "piano", "instrumental"] for e in ["wav", "mp3"]
    }:
        raise HTTPException(status_code=400, detail="Invalid stem name")
    path = (UPLOAD_DIR / project['stems_directory'] / stem_name).resolve()
    if not str(path).startswith(str(UPLOAD_DIR.resolve())) or not path.exists():
        raise HTTPException(status_code=404, detail="Stem not found")
    media_type = "audio/mpeg" if path.suffix == ".mp3" else "audio/wav"
    return FileResponse(str(path), media_type=media_type)


# Lyrics Generation
@api_router.post("/projects/{project_id}/generate-lyrics", response_model=LyricsResponse)
async def generate_lyrics(project_id: str, request: LyricsRequest):
    project = await db.projects.find_one({"id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    base_url = request.ollama_base_url or DEFAULT_OLLAMA_BASE_URL
    model = request.ollama_model or DEFAULT_OLLAMA_MODEL

    # Auto-detect loaded model when none specified
    if not model:
        try:
            detected = await ollama_list_models(base_url)
            if detected:
                model = detected[0]["name"]
                logger.info(f"Auto-detected LM Studio model: {model}")
        except Exception as _e:
            logger.warning(f"Could not auto-detect model from {base_url}: {_e}")

    # Preset style prompts
    style_prompts = {
        "trap": "Create trap-style rap lyrics with modern slang, references to success, money, and lifestyle. Confident, boastful tone with catchy hooks.",
        "boom_bap": "Write old-school boom bap rap lyrics with clever wordplay, storytelling, and conscious themes. Lyrical complexity and meaningful content.",
        "drill": "Drill rap lyrics with dark, aggressive themes and street narratives. Hard-hitting, direct, repetitive hooks.",
        "conscious": "Conscious rap lyrics addressing social issues and personal growth. Thoughtful, reflective language.",
        "melodic": "Melodic rap lyrics with singing elements. Catchy melodies and emotional themes.",
        "freestyle": "Freestyle rap lyrics with creative wordplay, metaphors, and spontaneous flow.",
    }

    mode = request.style

    # Helpers -------------------------------------------------
    async def get_defined_style_context(style_id: str) -> str:
        us = await db.user_styles.find_one({"id": style_id}, {"_id": 0})
        if not us:
            return ""
        samples = []
        if us.get('sample_lyrics'):
            samples.append(us['sample_lyrics'])
        samples.extend(us.get('text_samples') or [])
        samples.extend(us.get('audio_sample_transcripts') or [])
        joined_samples = "\n---\n".join(s.strip()[:800] for s in samples if s and s.strip())
        return (
            f"### Defined Style Reference\nName: {us.get('name')}\n"
            f"Description: {us.get('description')}\n"
            f"Samples:\n{joined_samples}\n"
            "Write in this user's style."
        )

    async def build_learned_prompt() -> str:
        profile = await db.profiles.find_one({"id": "default"}, {"_id": 0})
        if not profile or not profile.get('corpus'):
            raise HTTPException(
                status_code=400,
                detail="Learned Style requires a profile corpus. Add at least one work in the 'My Profile' tab."
            )
        fingerprint = profile.get('fingerprint') or await asyncio.to_thread(heuristic_fingerprint, profile['corpus'])
        samples = await asyncio.to_thread(select_representative_samples, profile['corpus'], 3)
        llm_theme = profile.get('llm_theme_summary') if request.use_llm_theme else None
        bias = request.learned_bias if request.learned_bias is not None else profile.get('fingerprint_bias', 0.5)
        user_brief = request.custom_prompt or "Write a new original piece in my voice."
        return await asyncio.to_thread(build_learned_style_prompt, user_brief, fingerprint, samples, llm_theme, bias)

    # Build prompt by mode ------------------------------------
    if mode == "learned":
        base_prompt = await build_learned_prompt()

    elif mode == "defined":
        if not request.user_style_id:
            raise HTTPException(
                status_code=400,
                detail="Defined mode requires a user_style_id. Create a style in the 'My Styles' tab first."
            )
        defined_ctx = await get_defined_style_context(request.user_style_id)
        if not defined_ctx:
            raise HTTPException(
                status_code=400,
                detail=f"Style '{request.user_style_id}' not found or has no content. Create or update the style first."
            )
        brief = request.custom_prompt or "Write new original lyrics."
        base_prompt = f"{defined_ctx}\n\n### Creative brief\n{brief}\n\nWrite AT LEAST 24 bars. Output raw lyric lines only — no headers, no markdown."

    elif mode == "blend":
        if not request.user_style_id:
            raise HTTPException(
                status_code=400,
                detail="Blend mode requires a user_style_id. Create a style in the 'My Styles' tab first."
            )
        learned_prompt = await build_learned_prompt()
        defined_ctx = await get_defined_style_context(request.user_style_id)
        weight = max(0.0, min(1.0, request.blend_weight or 0.5))
        bias_note = (
            f"Blend: {round((1 - weight) * 100)}% learned artist voice, "
            f"{round(weight * 100)}% defined style below.\n\n{defined_ctx}"
        )
        base_prompt = learned_prompt + "\n\n" + bias_note

    else:
        # Preset
        preset_text = style_prompts.get(mode, "Create original rap lyrics with creative wordplay and engaging flow.")
        brief = f"{preset_text}"
        if request.custom_prompt:
            brief += f"\n\nAdditional: {request.custom_prompt}"
        base_prompt = brief + "\n\nWrite AT LEAST 24 bars. Output raw lyric lines only — no headers, no markdown."

    # Structure mode (CEREMONIES GW04 dichotomy): PLACEHOLDER CADENCE keeps the
    # original bar/rhyme structure and rewrites content; FRESH builds new
    # structure from the final beat. Sent by the frontend, honored here.
    structure_mode = (request.structure_mode or "").strip().lower()
    if structure_mode == "placeholder":
        original = (project.get("original_transcription") or "").strip()
        if original:
            base_prompt += (
                "\n\n### Structure mode: PLACEHOLDER CADENCE\n"
                "Keep the bar count, line lengths, and rhyme scheme of the ORIGINAL lyrics below — "
                "rewrite the content only (new words, new themes, same skeleton). Match line-for-line.\n\n"
                f"### Original lyrics (structure to preserve)\n{original[:2000]}"
            )
        else:
            base_prompt += (
                "\n\n### Structure mode: PLACEHOLDER CADENCE\n"
                "No original transcription is available for this track — write a conventional "
                "verse/hook structure (24-32 bars) with a tight, consistent rhyme scheme."
            )
    elif structure_mode == "fresh":
        base_prompt += (
            "\n\n### Structure mode: FRESH DECONSTRUCTION\n"
            "Ignore any original song structure — build a NEW phonetic architecture from the "
            "final morphed beat: choose your own section layout, bar counts, and rhyme patterns."
        )

    # Call Ollama ---------------------------------------------
    try:
        system_msg = (
            "You are a professional rap lyricist. Output ONLY the song lyrics — no explanations, "
            "no section headers like (Verse), (Hook), (Bridge), no markdown formatting like ** or *, "
            "no horizontal rules, no preamble. Just the raw lyric lines, 24-32 bars minimum."
        )
        generated_lyrics = await ollama_generate(
            base_url=base_url, model=model, prompt=base_prompt,
            system=system_msg, temperature=0.9,
            api_key=request.llm_api_key or "",
        )
        if not generated_lyrics:
            raise HTTPException(status_code=500, detail="LLM returned empty response")

        # Persist to project
        await db.projects.update_one(
            {"id": project_id},
            {"$set": {
                "lyrics": generated_lyrics,
                "style": mode,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )

        # Auto-add generated lyrics to the user's profile corpus (learning feedback loop)
        # Only in learned/blend modes where the corpus is actively used
        if mode in ("learned", "blend"):
            try:
                await add_to_profile_corpus(
                    text=generated_lyrics,
                    source='generated',
                    title=f"{project.get('name', 'project')} — {mode}",
                )
            except Exception as e:
                logger.warning(f"Could not add to profile corpus: {e}")

        return LyricsResponse(lyrics=generated_lyrics, style=mode)

    except HTTPException:
        raise
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=f"Could not connect to AI server at {base_url}. Ensure LM Studio (or Ollama) is running."
        )
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=503,
            detail=f"AI server at {base_url} timed out — model may be too slow or server is overloaded. Try a smaller/faster model."
        )
    except Exception as e:
        logger.error(f"Lyrics generation error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate lyrics: {str(e)}")

# User Style Management
@api_router.post("/user-styles", response_model=UserStyle)
async def create_user_style(style: UserStyleCreate):
    style_obj = UserStyle(**style.dict())
    style_dict = style_obj.dict()
    style_dict['created_at'] = style_dict['created_at'].isoformat()
    await db.user_styles.insert_one(style_dict)
    return style_obj

@api_router.get("/user-styles", response_model=List[UserStyle])
async def get_user_styles():
    styles = await db.user_styles.find().to_list(1000)
    for style in styles:
        if isinstance(style.get('created_at'), str):
            style['created_at'] = datetime.fromisoformat(style['created_at'])
    return [UserStyle(**style) for style in styles]

@api_router.delete("/user-styles/{style_id}")
async def delete_user_style(style_id: str):
    result = await db.user_styles.delete_one({"id": style_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User style not found")
    return {"message": "User style deleted successfully"}

@api_router.post("/user-styles/{style_id}/text-sample", response_model=UserStyle)
async def add_text_sample_to_style(style_id: str, body: UserStyleSampleAdd):
    """Append a text sample to a defined style."""
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="Empty sample")
    result = await db.user_styles.update_one(
        {"id": style_id},
        {"$push": {"text_samples": body.text.strip()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Style not found")
    updated = await db.user_styles.find_one({"id": style_id}, {"_id": 0})
    if isinstance(updated.get('created_at'), str):
        updated['created_at'] = datetime.fromisoformat(updated['created_at'])
    return UserStyle(**updated)

@api_router.post("/user-styles/{style_id}/audio-sample", response_model=UserStyle)
async def add_audio_sample_to_style(style_id: str, file: UploadFile = File(...)):
    """Transcribe an audio sample (local Whisper) and append the transcript to a defined style."""
    style = await db.user_styles.find_one({"id": style_id})
    if not style:
        raise HTTPException(status_code=404, detail="Style not found")

    # Save temp
    suffix = Path(file.filename or "").suffix or ".wav"
    tmp_path = UPLOAD_DIR / f"style_{style_id}_sample{suffix}"
    await asyncio.to_thread(_save_upload_sync, file.file, tmp_path)

    try:
        result = await asyncio.to_thread(whisper_transcribe, str(tmp_path))
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass

    text = result.get('text', '').strip()
    if not text:
        raise HTTPException(status_code=422, detail="Whisper returned empty transcription")

    await db.user_styles.update_one(
        {"id": style_id},
        {"$push": {"audio_sample_transcripts": text}},
    )
    updated = await db.user_styles.find_one({"id": style_id}, {"_id": 0})
    if isinstance(updated.get('created_at'), str):
        updated['created_at'] = datetime.fromisoformat(updated['created_at'])
    return UserStyle(**updated)


# -------------------- Profile / Corpus / Fingerprint --------------------
@api_router.get("/profile", response_model=Profile)
async def get_profile():
    profile = await db.profiles.find_one({"id": "default"}, {"_id": 0})
    if not profile:
        profile = Profile().dict()
        to_insert = profile.copy()
        await db.profiles.insert_one(to_insert)
    # Normalize datetimes for Pydantic
    if isinstance(profile.get('fingerprint_updated_at'), str):
        try:
            profile['fingerprint_updated_at'] = datetime.fromisoformat(profile['fingerprint_updated_at'])
        except Exception:
            profile['fingerprint_updated_at'] = None
    for item in profile.get('corpus', []):
        if isinstance(item.get('created_at'), str):
            try:
                item['created_at'] = datetime.fromisoformat(item['created_at'])
            except Exception:
                item['created_at'] = datetime.now(timezone.utc)
    return Profile(**profile)

@api_router.post("/profile/corpus", response_model=Profile)
async def add_corpus_text(body: ProfileCorpusAdd):
    if not body.text.strip():
        raise HTTPException(status_code=400, detail="Empty text")
    await add_to_profile_corpus(body.text, source=body.source, title=body.title)
    return await get_profile()

@api_router.post("/profile/corpus/audio", response_model=Profile)
async def add_corpus_audio(file: UploadFile = File(...), title: Optional[str] = None):
    """Upload audio, transcribe with local Whisper, add to profile corpus."""
    suffix = Path(file.filename or "").suffix or ".wav"
    tmp_path = UPLOAD_DIR / f"corpus_audio{suffix}"
    await asyncio.to_thread(_save_upload_sync, file.file, tmp_path)
    try:
        result = await asyncio.to_thread(whisper_transcribe, str(tmp_path))
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
    text = result.get('text', '').strip()
    if not text:
        raise HTTPException(status_code=422, detail="Whisper returned empty transcription")
    await add_to_profile_corpus(text, source='audio_upload', title=title or file.filename)
    return await get_profile()

@api_router.delete("/profile/corpus/{item_id}")
async def delete_corpus_item(item_id: str):
    result = await db.profiles.update_one(
        {"id": "default"},
        {"$pull": {"corpus": {"id": item_id}}},
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Corpus item not found")
    return {"message": "Removed"}

@api_router.put("/profile/bias")
async def update_fingerprint_bias(bias: float):
    if bias < 0.0 or bias > 1.0:
        raise HTTPException(status_code=400, detail="bias must be 0..1")
    await db.profiles.update_one(
        {"id": "default"},
        {"$set": {"fingerprint_bias": float(bias)}},
        upsert=True,
    )
    return {"fingerprint_bias": bias}

@api_router.post("/profile/fingerprint/compute", response_model=Profile)
async def compute_fingerprint(body: FingerprintComputeRequest):
    profile = await db.profiles.find_one({"id": "default"}, {"_id": 0})
    if not profile or not profile.get('corpus'):
        raise HTTPException(
            status_code=400,
            detail="No corpus. Add at least one work to your profile first.",
        )
    corpus = profile['corpus']
    fingerprint = await asyncio.to_thread(heuristic_fingerprint, corpus)

    llm_theme_summary: Optional[str] = None
    if body.use_llm_theme:
        # Summarize themes/tone/voice via Ollama
        base_url = body.ollama_base_url or DEFAULT_OLLAMA_BASE_URL
        model = body.ollama_model or DEFAULT_OLLAMA_MODEL
        # Take up to ~8000 chars of corpus (most recent)
        joined = "\n\n---\n\n".join(
            (c.get('text') or '')[:1200] for c in corpus[-12:]
        )[:8000]
        theme_prompt = (
            "Below is a corpus of an artist's rap lyrics. In 4-6 concise bullet points, "
            "describe their recurring THEMES, emotional TONE, distinctive VOICE, and the "
            "personas or perspectives they write from. Be specific and observational, not generic. "
            "Do not mention that you are an AI.\n\n"
            f"=== CORPUS ===\n{joined}\n=== END CORPUS ==="
        )
        try:
            llm_theme_summary = await ollama_generate(
                base_url=base_url, model=model, prompt=theme_prompt,
                system="You are a music critic analyzing an artist's style.",
                temperature=0.4,
                api_key=body.llm_api_key or "",
            )
        except HTTPException:
            logger.warning("Ollama theme pass failed; storing heuristic-only fingerprint")
        except Exception as e:
            logger.warning(f"Ollama theme pass error: {e}")

    update = {
        "fingerprint": fingerprint,
        "fingerprint_updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if llm_theme_summary:
        update["llm_theme_summary"] = llm_theme_summary
    if body.bias is not None:
        update["fingerprint_bias"] = max(0.0, min(1.0, float(body.bias)))

    await db.profiles.update_one({"id": "default"}, {"$set": update}, upsert=True)
    return await get_profile()


# -------------------- Whisper Transcription --------------------
@api_router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio(file: UploadFile = File(...)):
    """General-purpose local Whisper transcription."""
    suffix = Path(file.filename or "").suffix or ".wav"
    tmp_path = UPLOAD_DIR / f"transcribe{suffix}"
    await asyncio.to_thread(_save_upload_sync, file.file, tmp_path)
    try:
        result = await asyncio.to_thread(whisper_transcribe, str(tmp_path))
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
    return TranscribeResponse(**result)

# File Download
@api_router.get("/files/{filename}")
async def download_file(filename: str):
    file_path = (UPLOAD_DIR / filename).resolve()
    if not str(file_path).startswith(str(UPLOAD_DIR.resolve())):
        raise HTTPException(status_code=400, detail="Invalid path")
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)

# Export Project
@api_router.get("/projects/{project_id}/export")
async def export_project(project_id: str):
    project = await db.projects.find_one({"id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Create export package info
    export_data = {
        "project_name": project["name"],
        "has_audio": bool(project.get("transformed_file") or project.get("original_file")),
        "has_lyrics": bool(project.get("lyrics")),
        "audio_file": project.get("transformed_file") or project.get("original_file"),
        "lyrics": project.get("lyrics"),
        "style": project.get("style"),
        "created_at": project.get("created_at"),
        "ready_for_export": bool(project.get("transformed_file") and project.get("lyrics"))
    }
    
    return export_data

# Download Lyrics as Text File
@api_router.get("/projects/{project_id}/download-lyrics")
async def download_lyrics(project_id: str):
    project = await db.projects.find_one({"id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    if not project.get("lyrics"):
        raise HTTPException(status_code=404, detail="No lyrics found for this project")
    
    # Create lyrics file content
    lyrics_content = f"""Title: {project['name']}
Style: {project.get('style', 'Unknown')}
Generated: {project.get('updated_at', 'Unknown')}
Copyright: Original Work - Ready for Publishing

---

{project['lyrics']}

---

Generated by Beat Maker AI
This work is original and ready for copyright registration.
"""
    
    # Create temporary file
    lyrics_filename = f"{project['name'].replace(' ', '_')}_lyrics.txt"
    lyrics_path = UPLOAD_DIR / lyrics_filename
    
    with open(lyrics_path, "w", encoding="utf-8") as f:
        f.write(lyrics_content)
    
    return FileResponse(
        lyrics_path, 
        filename=lyrics_filename,
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename={lyrics_filename}"}
    )

# Ollama Integration Endpoints
@api_router.get("/ollama/config")
async def ollama_config():
    """Return the default Ollama config (base_url + model) the server is pre-configured with"""
    return {"base_url": DEFAULT_OLLAMA_BASE_URL, "model": DEFAULT_OLLAMA_MODEL}

@api_router.post("/ollama/test")
async def ollama_test_connection(req: OllamaTestRequest):
    """Test connection to an Ollama server and return its available models"""
    base_url = (req.base_url or DEFAULT_OLLAMA_BASE_URL).rstrip('/')
    try:
        models_raw = await ollama_list_models(base_url, req.api_key or "")
        models = []
        for m in models_raw:
            details = m.get('details', {}) or {}
            models.append({
                "name": m.get('name', 'unknown'),
                "size": m.get('size', 0),
                "parameter_size": details.get('parameter_size', ''),
                "quantization_level": details.get('quantization_level', ''),
            })
        return {
            "connected": True,
            "base_url": base_url,
            "message": f"Connected. Found {len(models)} model(s).",
            "models": models,
        }
    except httpx.ConnectError:
        return {
            "connected": False,
            "base_url": base_url,
            "message": f"Could not reach AI server at {base_url}. Is LM Studio (or Ollama) running?",
            "models": [],
        }
    except httpx.TimeoutException:
        return {
            "connected": False,
            "base_url": base_url,
            "message": "Connection to AI server timed out.",
            "models": [],
        }
    except Exception as e:
        logger.error(f"Ollama test error: {e}")
        return {
            "connected": False,
            "base_url": base_url,
            "message": f"Error: {str(e)}",
            "models": [],
        }

# -------------------- Voice Clone (Gateway 05) --------------------

@api_router.post("/projects/{project_id}/voice-sample")
async def upload_voice_sample(project_id: str, file: UploadFile = File(...)):
    project = await db.projects.find_one({"id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    suffix = Path(file.filename or "sample.wav").suffix or ".wav"
    sample_path = UPLOAD_DIR / f"{project_id}_voice_sample{suffix}"
    await asyncio.to_thread(_save_upload_sync, file.file, sample_path)
    await db.projects.update_one(
        {"id": project_id},
        {"$set": {"voice_sample_file": sample_path.name, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"status": "ok", "file": sample_path.name}


class VoiceCloneRequest(BaseModel):
    lyrics: Optional[str] = None


@api_router.post("/projects/{project_id}/voice-clone")
async def start_voice_clone(project_id: str, body: VoiceCloneRequest = VoiceCloneRequest()):
    project = await db.projects.find_one({"id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.get("voice_sample_file"):
        raise HTTPException(status_code=400, detail="No voice sample uploaded for this project")

    # Pre-check: verify Voice Clone Server is reachable
    if not VOICE_CLONE_URL:
        raise HTTPException(status_code=503, detail="Voice clone service is not configured")

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as health_client:
            health_resp = await health_client.get(f"{VOICE_CLONE_URL}/health")
            health_resp.raise_for_status()
    except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError, OSError) as e:
        logger.warning(f"Voice clone health check failed: {e}")
        raise HTTPException(status_code=503, detail="Voice clone service is unavailable")

    # Accept lyrics from request body if project DB entry doesn't have them yet
    lyrics = (project.get("lyrics") or "").strip() or (body.lyrics or "").strip()
    if not lyrics:
        raise HTTPException(status_code=400, detail="No lyrics found — complete Gateway 04 first")

    # Persist if they came only from the request body
    if not (project.get("lyrics") or "").strip() and lyrics:
        await db.projects.update_one(
            {"id": project_id},
            {"$set": {"lyrics": lyrics, "updated_at": datetime.now(timezone.utc).isoformat()}},
        )
    await db.projects.update_one(
        {"id": project_id},
        {"$set": {"voice_clone_status": "processing", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    await create_bounded_task(_run_voice_clone(project_id), name=f"voice-clone-{project_id}")
    return {"status": "processing"}


async def _run_voice_clone(project_id: str):
    try:
        project = await db.projects.find_one({"id": project_id})
        sample_path = UPLOAD_DIR / project["voice_sample_file"]
        lyrics = project.get("lyrics", "")
        loop = asyncio.get_event_loop()
        # VOICE_CLONE_URL is guaranteed set — the endpoint 503s when it's empty.
        # The server speaks the shared /health + /clone wire contract
        # (backend/xtts_server.py and backend/f5tts_server.py both implement it).
        out_path = await loop.run_in_executor(None, _call_voice_clone_server, str(sample_path), lyrics)
        await db.projects.update_one(
            {"id": project_id},
            {"$set": {
                "voice_clone_status": "complete",
                "voice_clone_file": Path(out_path).name,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }}
        )
        logger.info(f"Voice clone complete for {project_id}")
    except Exception as e:
        logger.error(f"Voice clone failed for {project_id}: {e}")
        await db.projects.update_one(
            {"id": project_id},
            {"$set": {"voice_clone_status": "failed", "voice_clone_error": str(e),
                      "updated_at": datetime.now(timezone.utc).isoformat()}}
        )


def _clean_lyrics_for_tts(text: str) -> str:
    """Strip LLM markdown/section headers so the TTS engine doesn't speak them literally."""
    import re
    # Strip bold/italic markdown
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    # Strip any standalone (Section) or [Section] label line — (Verse 1), (Hook), [Beat drops], ...
    text = re.sub(r'^\s*[\(\[].*?[\)\]]\s*$', '', text, flags=re.MULTILINE)
    # Strip markdown heading markers
    text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)
    # Strip horizontal rule lines
    text = re.sub(r'^\s*-{2,}\s*$', '', text, flags=re.MULTILINE)
    # Strip lines that are ONLY punctuation/symbols (no word characters)
    text = re.sub(r'^\s*[^\w\s]+\s*$', '', text, flags=re.MULTILINE)
    # Collapse multiple blank lines to a single blank line
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()
    # Truncate to 800 chars for TTS reliability
    if len(text) > 800:
        text = text[:800].rsplit('\n', 1)[0].strip()
    return text


def _call_voice_clone_server(sample_path: str, lyrics: str) -> str:
    import requests

    clean = _clean_lyrics_for_tts(lyrics)

    ref_transcript = _remote_transcribe(sample_path)

    with open(sample_path, "rb") as ref_f:
        resp = requests.post(
            f"{VOICE_CLONE_URL}/clone",
            data={"text": clean, "ref_text": ref_transcript},
            files={"reference": (Path(sample_path).name, ref_f)},
            timeout=600,
        )
    resp.raise_for_status()
    out_path = str(UPLOAD_DIR / f"{Path(sample_path).stem}_cloned.wav")
    with open(out_path, "wb") as out_f:
        out_f.write(resp.content)
    return out_path


@api_router.get("/projects/{project_id}/voice-clone-status")
async def voice_clone_status_endpoint(project_id: str):
    project = await db.projects.find_one({"id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    status = project.get("voice_clone_status", "pending")
    return {
        "status": status,
        "error": project.get("voice_clone_error") if status == "failed" else None,
    }


@api_router.get("/projects/{project_id}/download-vocal")
async def download_vocal(project_id: str):
    project = await db.projects.find_one({"id": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.get("voice_clone_status") != "complete":
        raise HTTPException(status_code=404, detail="No cloned vocal available — voice clone is not complete")
    if not project.get("voice_clone_file"):
        raise HTTPException(status_code=404, detail="No cloned vocal available")
    vocal_path = UPLOAD_DIR / project["voice_clone_file"]
    if not vocal_path.exists():
        raise HTTPException(status_code=404, detail="Vocal file not found on disk")
    return FileResponse(
        str(vocal_path),
        media_type="audio/wav",
        filename="CLONED_VOCAL.wav",
        headers={"Content-Disposition": "attachment; filename=CLONED_VOCAL.wav"}
    )


# Include the router in the main app
app.include_router(api_router)

# Serve the pre-built frontend (frontend/dist/) when present — enables the
# standalone .exe mode where no Node/Vite dev server is needed.
_FRONTEND_DIST = ROOT_DIR.parent / "frontend" / "dist"
if _FRONTEND_DIST.is_dir():
    from fastapi.staticfiles import StaticFiles
    from starlette.responses import FileResponse as _FR

    app.mount("/assets", StaticFiles(directory=str(_FRONTEND_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """SPA catch-all: serve index.html for any non-API route."""
        candidate = _FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return _FR(str(candidate))
        return _FR(str(_FRONTEND_DIST / "index.html"))

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("startup")
async def startup_reset_stale_jobs():
    """Any job still 'processing' at startup was orphaned by a crash/restart — reset it."""
    r1 = await db.projects.update_many(
        {"transform_status": "processing"},
        {"$set": {"transform_status": "pending", "transform_error": None}},
    )
    r2 = await db.projects.update_many(
        {"voice_clone_status": "processing"},
        {"$set": {"voice_clone_status": "pending", "voice_clone_error": None}},
    )
    r3 = await db.projects.update_many(
        {"morph_status": "processing"},
        {"$set": {"morph_status": "pending", "morph_error": None}},
    )
    total = r1.modified_count + r2.modified_count + r3.modified_count
    if total:
        logger.info(f"Reset {total} orphaned job(s) to 'pending' on startup")


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
