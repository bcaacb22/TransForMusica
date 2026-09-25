"""
Demucs Stem Separation Server — run on Windows GPU machine.

Install:
  pip install demucs fastapi uvicorn python-multipart faster-whisper

Run:
  python demucs_server.py
"""

import io
import os
import tempfile
import zipfile
from pathlib import Path

import torch
import uvicorn
from fastapi import FastAPI, File, UploadFile
from fastapi.responses import Response

app = FastAPI()

_demucs_model = None
_whisper_model = None


def _get_demucs_model():
    global _demucs_model
    if _demucs_model is None:
        from demucs.pretrained import get_model
        model = get_model("htdemucs_6s")
        model.eval()
        device = "cuda" if torch.cuda.is_available() else "cpu"
        model.to(device)
        _demucs_model = model
    return _demucs_model


def _get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        device = "cuda" if torch.cuda.is_available() else "cpu"
        compute = "float16" if device == "cuda" else "int8"
        _whisper_model = WhisperModel("tiny", device=device, compute_type=compute)
    return _whisper_model


@app.get("/health")
def health():
    try:
        import demucs  # noqa: F401
        demucs_ok = True
    except ImportError:
        demucs_ok = False
    cuda_ok = torch.cuda.is_available()
    device = "cuda" if cuda_ok else "cpu"
    return {
        "status": "ok" if demucs_ok else "demucs_not_installed",
        "model": "htdemucs_6s",
        "device": device,
        "demucs_installed": demucs_ok,
    }


@app.post("/separate")
async def separate(audio: UploadFile = File(...)):
    from demucs.audio import AudioFile, save_audio
    from demucs.apply import apply_model

    suffix = Path(audio.filename or "audio.mp3").suffix or ".mp3"
    tmp_fd, audio_path = tempfile.mkstemp(suffix=suffix)
    os.close(tmp_fd)

    try:
        with open(audio_path, "wb") as f:
            f.write(await audio.read())

        model = _get_demucs_model()
        device = next(model.parameters()).device

        wav = AudioFile(audio_path).read(
            streams=0,
            samplerate=model.samplerate,
            channels=model.audio_channels,
        )

        ref = wav.mean(0)
        wav = (wav - ref.mean()) / ref.std()

        with torch.no_grad():
            sources = apply_model(
                model, wav[None].to(device),
                device=device, shifts=1, split=True, overlap=0.25, progress=False,
            )[0]

        sources = sources * ref.std() + ref.mean()
        stem_names = model.sources

        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for i, name in enumerate(stem_names):
                stem_fd, stem_path = tempfile.mkstemp(suffix=".wav")
                os.close(stem_fd)
                try:
                    save_audio(sources[i].cpu(), stem_path, samplerate=model.samplerate)
                    zf.write(stem_path, f"{name}.wav")
                finally:
                    try:
                        os.unlink(stem_path)
                    except Exception:
                        pass

        zip_buf.seek(0)
        return Response(
            content=zip_buf.read(),
            media_type="application/zip",
            headers={"Content-Disposition": "attachment; filename=stems.zip"},
        )

    except Exception as e:
        import traceback
        return Response(
            content=f"Separate failed: {e}\n{traceback.format_exc()}",
            status_code=500,
            media_type="text/plain",
        )
    finally:
        try:
            os.unlink(audio_path)
        except Exception:
            pass


@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...), trim_seconds: int = 60):
    import subprocess

    suffix = Path(audio.filename or "audio.mp3").suffix or ".mp3"
    tmp_fd, audio_path = tempfile.mkstemp(suffix=suffix)
    os.close(tmp_fd)
    trimmed_path = None
    try:
        with open(audio_path, "wb") as f:
            f.write(await audio.read())

        transcribe_path = audio_path
        if trim_seconds > 0:
            try:
                trimmed_fd, trimmed_path = tempfile.mkstemp(suffix=".wav")
                os.close(trimmed_fd)
                result = subprocess.run(
                    ["ffmpeg", "-y", "-i", audio_path, "-t", str(trim_seconds),
                     "-ac", "1", "-ar", "16000", trimmed_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    encoding="utf-8",
                    errors="replace",
                )
                if result.returncode == 0:
                    transcribe_path = trimmed_path
            except Exception:
                pass

        wm = _get_whisper_model()
        segs, _ = wm.transcribe(transcribe_path, beam_size=1, language="en")
        text = " ".join(s.text for s in segs).strip()
        return {"text": text}
    finally:
        try:
            os.unlink(audio_path)
        except Exception:
            pass
        if trimmed_path:
            try:
                os.unlink(trimmed_path)
            except Exception:
                pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8600))
    uvicorn.run(app, host="0.0.0.0", port=port)
