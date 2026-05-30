"""
XTTS-v2 Voice Clone Server — run this on your local GPU machine (RTX 3080).

Install:
  pip install TTS torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
  pip install fastapi uvicorn python-multipart

Run:
  python xtts_server.py

Expose via Tailscale Funnel:
  tailscale funnel 8500

Then set in Transformusic backend/.env:
  VOICE_CLONE_URL="https://yourpc.tail1234.ts.net"
"""

import os
import logging
import tempfile
from pathlib import Path

import torch
import uvicorn
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s - %(message)s")
logger = logging.getLogger("xtts-server")

app = FastAPI()

device = "cuda" if torch.cuda.is_available() else "cpu"
logger.info(f"Loading XTTS-v2 on {device}...")

from TTS.api import TTS
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
logger.info(f"XTTS-v2 ready on {device}")


@app.get("/health")
def health():
    return {"status": "ok", "device": device, "model": "xtts_v2"}


@app.post("/clone")
async def clone(
    text: str = Form(...),
    language: str = Form(default="en"),
    reference: UploadFile = File(...),
):
    ref_suffix = Path(reference.filename or "ref.wav").suffix or ".wav"

    with tempfile.NamedTemporaryFile(suffix=ref_suffix, delete=False) as ref_f:
        ref_f.write(await reference.read())
        ref_path = ref_f.name

    out_fd, out_path = tempfile.mkstemp(suffix=".wav")
    os.close(out_fd)

    try:
        logger.info(f"Synthesizing {len(text)} chars on {device}...")
        tts.tts_to_file(
            text=text,
            speaker_wav=ref_path,
            language=language,
            file_path=out_path,
        )
        logger.info("Synthesis complete")
        return FileResponse(out_path, media_type="audio/wav", filename="cloned_vocal.wav")
    finally:
        try:
            os.unlink(ref_path)
        except Exception:
            pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8500))
    uvicorn.run(app, host="0.0.0.0", port=port)
