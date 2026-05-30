"""
F5-TTS Voice Clone Server — run this on your Windows GPU machine.

Install:
  pip install f5-tts

Run:
  python f5tts_server.py

Requires: reference WAV clip (6-30s clean vocal) sent with each request.
"""

import os
import tempfile
import uvicorn
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok", "model": "f5-tts"}


@app.post("/clone")
async def clone(
    text: str = Form(...),
    ref_text: str = Form(default=""),
    reference: UploadFile = File(...),
):
    ref_suffix = Path(reference.filename or "ref.wav").suffix or ".wav"

    with tempfile.NamedTemporaryFile(suffix=ref_suffix, delete=False) as ref_f:
        ref_f.write(await reference.read())
        ref_path = ref_f.name

    out_fd, out_path = tempfile.mkstemp(suffix=".wav")
    os.close(out_fd)

    try:
        from f5_tts.api import F5TTS
        tts = F5TTS()
        tts.infer(
            ref_file=ref_path,
            ref_text=ref_text,
            gen_text=text,
            file_wave=out_path,
            seed=-1,
        )
        return FileResponse(out_path, media_type="audio/wav", filename="cloned_vocal.wav")
    finally:
        try:
            os.unlink(ref_path)
        except Exception:
            pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8500))
    uvicorn.run(app, host="0.0.0.0", port=port)
