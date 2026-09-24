"""Transformusic backend API tests (pytest, live server).

Requires a RUNNING backend + MongoDB. Point at the fork with:
    REACT_APP_BACKEND_URL=http://localhost:8001 pytest backend/tests/backend_test.py
LLM-dependent tests are skipped unless the mock Ollama server is up on :11434.
"""
import os
import io
import time
import zipfile
import pytest
import requests
import numpy as np
import soundfile as sf

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api"

# --- helpers ---
def _make_short_mp3():
    """Create a ~3 second sine-wave WAV -> MP3-like payload. Use WAV with audio/mpeg trick won't work.
    Backend allows audio/mpeg, audio/wav, audio/mp3, audio/x-wav. We'll send a WAV.
    """
    sr = 22050
    t = np.linspace(0, 3.0, int(sr * 3.0), endpoint=False)
    y = 0.3 * np.sin(2 * np.pi * 220 * t) + 0.2 * np.sin(2 * np.pi * 440 * t)
    buf = io.BytesIO()
    sf.write(buf, y.astype(np.float32), sr, format="WAV")
    buf.seek(0)
    return buf


def _mock_ollama_up() -> bool:
    """True if the mock Ollama server (2 fake models, canned lyrics) is reachable."""
    try:
        requests.get("http://localhost:11434/api/tags", timeout=2)
        return True
    except Exception:
        return False


_needs_mock_ollama = pytest.mark.skipif(
    not _mock_ollama_up(), reason="mock Ollama server not running on :11434")
@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    return s

# --- Health ---
def test_root_health(client):
    r = client.get(f"{API}/")
    assert r.status_code == 200
    assert "message" in r.json()

# --- Ollama config/test ---
def test_ollama_config(client):
    r = client.get(f"{API}/ollama/config")
    assert r.status_code == 200
    data = r.json()
    assert "base_url" in data and "model" in data

@_needs_mock_ollama
def test_ollama_test_success(client):
    r = client.post(f"{API}/ollama/test", json={"base_url": "http://localhost:11434"})
    assert r.status_code == 200
    d = r.json()
    assert d["connected"] is True
    assert len(d["models"]) == 2
    names = [m["name"] for m in d["models"]]
    assert "llama3.2:latest" in names

def test_ollama_test_unreachable(client):
    r = client.post(f"{API}/ollama/test", json={"base_url": "http://127.0.0.1:59999"})
    assert r.status_code == 200  # must NOT 500
    d = r.json()
    assert d["connected"] is False
    assert d["models"] == []

# --- Project CRUD ---
@pytest.fixture(scope="module")
def project_id(client):
    r = client.post(f"{API}/projects", json={"name": "TEST_beat_project"})
    assert r.status_code == 200
    pid = r.json()["id"]
    return pid

def test_get_project(client, project_id):
    r = client.get(f"{API}/projects/{project_id}")
    assert r.status_code == 200
    assert r.json()["id"] == project_id
    assert r.json()["name"] == "TEST_beat_project"

# --- Upload ---
def test_upload_file(client, project_id):
    buf = _make_short_mp3()
    files = {"file": ("test.wav", buf, "audio/wav")}
    r = client.post(f"{API}/projects/{project_id}/upload", files=files)
    assert r.status_code == 200, r.text
    assert "filename" in r.json()

# --- Transform (async task: trigger + poll transform-status) ---
def test_transform_and_download(client, project_id):
    r = client.post(f"{API}/projects/{project_id}/transform", timeout=60)
    assert r.status_code == 200, r.text
    assert r.json().get("status") == "processing"

    # Poll until complete/failed — a 3s sine wave through local Demucs + Basic
    # Pitch takes on the order of a minute on CPU.
    deadline = time.time() + 600
    final = None
    while time.time() < deadline:
        rs = client.get(f"{API}/projects/{project_id}/transform-status", timeout=30)
        assert rs.status_code == 200, rs.text
        data = rs.json()
        if data.get("status") in ("complete", "failed"):
            final = data
            break
        assert data.get("status") == "processing", f"unexpected status: {data}"
        time.sleep(3)
    assert final is not None, "transform did not finish within 600s"
    assert final.get("status") == "complete", f"transform failed: {final.get('error')}"
    assert len(final.get("midi_files", [])) >= 1
    assert len(final.get("musicxml_files", [])) >= 1

    # Download ZIP — proves stems artifacts exist server-side
    rz = client.get(f"{API}/projects/{project_id}/download-stems", timeout=300)
    assert rz.status_code == 200
    zbuf = io.BytesIO(rz.content)
    with zipfile.ZipFile(zbuf) as zf:
        names = zf.namelist()
    assert any(n.endswith(".mid") for n in names), f"no .mid in zip: {names}"
    assert any(n.endswith(".musicxml") for n in names), f"no .musicxml in zip: {names}"

# --- Generate Lyrics via Ollama (mock) ---
@_needs_mock_ollama
def test_generate_lyrics_ollama_success(client, project_id):
    payload = {
        "project_id": project_id,
        "style": "trap",
        "ollama_base_url": "http://localhost:11434",
        "ollama_model": "llama3.2:latest",
    }
    r = client.post(f"{API}/projects/{project_id}/generate-lyrics", json=payload, timeout=120)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["style"] == "trap"
    assert "Ollama" in d["lyrics"] or len(d["lyrics"]) > 20

    # Verify persisted
    rp = client.get(f"{API}/projects/{project_id}")
    assert rp.status_code == 200
    assert rp.json().get("lyrics")

def test_generate_lyrics_unreachable_ollama(client, project_id):
    payload = {
        "project_id": project_id,
        "style": "trap",
        "ollama_base_url": "http://127.0.0.1:59999",
        "ollama_model": "nope",
    }
    r = client.post(f"{API}/projects/{project_id}/generate-lyrics", json=payload, timeout=30)
    assert r.status_code == 503, f"expected 503, got {r.status_code}: {r.text}"

# --- Download lyrics (404 when no lyrics generated, 200+attachment when present) ---
def test_download_lyrics(client, project_id):
    r = client.get(f"{API}/projects/{project_id}/download-lyrics")
    # Lyrics only exist if a prior generate-lyrics call succeeded (mock Ollama
    # tests are skipped without the mock server). Both outcomes are valid contracts.
    if r.status_code == 200:
        assert "attachment" in r.headers.get("content-disposition", "").lower()
    else:
        assert r.status_code == 404, f"expected 200 or 404, got {r.status_code}"

# --- User Styles CRUD ---
def test_user_styles_crud(client):
    # Create
    payload = {"name": "TEST_style", "description": "test desc", "sample_lyrics": "sample"}
    r = client.post(f"{API}/user-styles", json=payload)
    assert r.status_code == 200, r.text
    sid = r.json()["id"]
    assert r.json()["name"] == "TEST_style"

    # List
    r2 = client.get(f"{API}/user-styles")
    assert r2.status_code == 200
    assert any(s["id"] == sid for s in r2.json())

    # Delete
    r3 = client.delete(f"{API}/user-styles/{sid}")
    assert r3.status_code == 200

    # Delete again -> 404
    r4 = client.delete(f"{API}/user-styles/{sid}")
    assert r4.status_code == 404


# =====================================================================
# Iteration 2: Profile / Corpus / Fingerprint / Learned Style / Whisper
# =====================================================================

OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3.2:latest"


def _reset_profile(client):
    """Reset default profile to known state by deleting all corpus items."""
    r = client.get(f"{API}/profile")
    if r.status_code != 200:
        return
    for it in r.json().get("corpus", []):
        client.delete(f"{API}/profile/corpus/{it['id']}")


# --- Profile auto-create ---
def test_profile_auto_create(client):
    _reset_profile(client)
    r = client.get(f"{API}/profile")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["id"] == "default"
    assert isinstance(d["corpus"], list)
    assert 0.0 <= d["fingerprint_bias"] <= 1.0


# --- Corpus add text / delete ---
def test_profile_add_and_delete_corpus(client):
    _reset_profile(client)
    sample = "I ride through the city with my heart on my sleeve\nEvery bar I breathe, every dream I believe"
    r = client.post(f"{API}/profile/corpus", json={"text": sample, "title": "TEST_work1", "source": "text_upload"})
    assert r.status_code == 200, r.text
    prof = r.json()
    assert len(prof["corpus"]) >= 1
    item = prof["corpus"][-1]
    assert "id" in item and item["source"] == "text_upload" and item["title"] == "TEST_work1"
    item_id = item["id"]

    # delete
    rd = client.delete(f"{API}/profile/corpus/{item_id}")
    assert rd.status_code == 200

    # verify gone
    rp = client.get(f"{API}/profile")
    assert not any(i["id"] == item_id for i in rp.json()["corpus"])


def test_profile_add_empty_rejected(client):
    r = client.post(f"{API}/profile/corpus", json={"text": "   ", "source": "manual"})
    assert r.status_code == 400


# --- Fingerprint compute heuristic only ---
def test_fingerprint_compute_heuristic(client):
    _reset_profile(client)
    lyrics = (
        "Running through the night, chasing every light\n"
        "Holding my pen tight, every word is a fight\n"
        "Shadow on the wall, hear the city call\n"
        "Stand or I fall, I rise above it all\n"
    )
    client.post(f"{API}/profile/corpus", json={"text": lyrics, "title": "TEST_fp1", "source": "text_upload"})
    r = client.post(f"{API}/profile/fingerprint/compute", json={"use_llm_theme": False})
    assert r.status_code == 200, r.text
    prof = r.json()
    fp = prof.get("fingerprint")
    assert fp is not None
    assert "corpus_stats" in fp
    assert "lexical" in fp and "top_words" in fp["lexical"]
    assert "phonetic" in fp
    assert "avg_syllables_per_line" in fp["phonetic"]
    assert "rhyme_density" in fp["phonetic"]
    assert "structural" in fp
    assert prof.get("llm_theme_summary") in (None, "")


@_needs_mock_ollama
def test_fingerprint_compute_with_llm(client):
    r = client.post(
        f"{API}/profile/fingerprint/compute",
        json={"use_llm_theme": True, "ollama_base_url": OLLAMA_URL, "ollama_model": OLLAMA_MODEL},
    )
    assert r.status_code == 200, r.text
    prof = r.json()
    assert prof.get("llm_theme_summary")
    assert len(prof["llm_theme_summary"]) > 5


def test_fingerprint_compute_no_corpus(client):
    _reset_profile(client)
    r = client.post(f"{API}/profile/fingerprint/compute", json={"use_llm_theme": False})
    assert r.status_code == 400


# --- Bias persistence ---
def test_profile_bias_persistence(client):
    r = client.put(f"{API}/profile/bias", params={"bias": 0.7})
    assert r.status_code == 200
    assert r.json()["fingerprint_bias"] == 0.7
    rp = client.get(f"{API}/profile")
    assert rp.json()["fingerprint_bias"] == 0.7


def test_profile_bias_out_of_range(client):
    r = client.put(f"{API}/profile/bias", params={"bias": 1.5})
    assert r.status_code == 400


# --- User Style text-sample / audio-sample ---
def test_user_style_text_sample(client):
    # create style
    r = client.post(f"{API}/user-styles", json={"name": "TEST_style_sample", "description": "d", "sample_lyrics": "s"})
    sid = r.json()["id"]
    try:
        ra = client.post(f"{API}/user-styles/{sid}/text-sample", json={"text": "Another sample bar"})
        assert ra.status_code == 200, ra.text
        d = ra.json()
        assert "Another sample bar" in d["text_samples"]
    finally:
        client.delete(f"{API}/user-styles/{sid}")


def test_user_style_text_sample_404(client):
    r = client.post(f"{API}/user-styles/does-not-exist/text-sample", json={"text": "x"})
    assert r.status_code == 404


# --- Whisper transcribe (sine wave -> empty text is acceptable) ---
def test_transcribe_endpoint(client):
    buf = _make_short_mp3()
    files = {"file": ("tone.wav", buf, "audio/wav")}
    r = client.post(f"{API}/transcribe", files=files, timeout=120)
    # First call may take ~15s to load model
    assert r.status_code == 200, r.text
    d = r.json()
    assert "text" in d
    assert "duration_seconds" in d


def test_profile_corpus_audio_endpoint(client):
    # Sine wave will produce empty transcript -> 422 acceptable, 200 also acceptable
    buf = _make_short_mp3()
    files = {"file": ("tone.wav", buf, "audio/wav")}
    r = client.post(f"{API}/profile/corpus/audio", files=files, timeout=120)
    assert r.status_code in (200, 422), f"expected 200 or 422 got {r.status_code}: {r.text}"


# --- Lyrics generate in learned mode ---
@_needs_mock_ollama
def test_generate_lyrics_learned_empty_corpus_400(client, project_id):
    _reset_profile(client)
    payload = {
        "style": "learned",
        "ollama_base_url": OLLAMA_URL,
        "ollama_model": OLLAMA_MODEL,
        "learned_bias": 0.5,
        "use_llm_theme": False,
    }
    r = client.post(f"{API}/projects/{project_id}/generate-lyrics", json=payload, timeout=30)
    assert r.status_code == 400, r.text


@_needs_mock_ollama
def test_generate_lyrics_learned_success(client, project_id):
    _reset_profile(client)
    # seed corpus
    client.post(f"{API}/profile/corpus", json={
        "text": "I was born in the dark, I rose with the spark\nWritten every bar with a permanent mark",
        "title": "TEST_seed",
        "source": "text_upload",
    })
    before = len(client.get(f"{API}/profile").json()["corpus"])
    payload = {
        "style": "learned",
        "ollama_base_url": OLLAMA_URL,
        "ollama_model": OLLAMA_MODEL,
        "learned_bias": 0.5,
        "use_llm_theme": False,
    }
    r = client.post(f"{API}/projects/{project_id}/generate-lyrics", json=payload, timeout=120)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["style"] == "learned"
    assert len(d["lyrics"]) > 10
    # verify corpus auto-grew with 'generated' item
    after = client.get(f"{API}/profile").json()["corpus"]
    assert len(after) == before + 1
    assert after[-1]["source"] == "generated"


@_needs_mock_ollama
def test_generate_lyrics_defined_with_user_style(client, project_id):
    cs = client.post(f"{API}/user-styles", json={
        "name": "TEST_defined_style",
        "description": "Aggressive, punchy",
        "sample_lyrics": "Hammer in the floor, knocking on the door",
    })
    sid = cs.json()["id"]
    try:
        payload = {
            "style": "defined",
            "user_style_id": sid,
            "ollama_base_url": OLLAMA_URL,
            "ollama_model": OLLAMA_MODEL,
        }
        r = client.post(f"{API}/projects/{project_id}/generate-lyrics", json=payload, timeout=120)
        assert r.status_code == 200, r.text
        assert r.json()["style"] == "defined"
    finally:
        client.delete(f"{API}/user-styles/{sid}")


@_needs_mock_ollama
def test_generate_lyrics_defined_missing_id(client, project_id):
    payload = {"style": "defined", "ollama_base_url": OLLAMA_URL, "ollama_model": OLLAMA_MODEL}
    r = client.post(f"{API}/projects/{project_id}/generate-lyrics", json=payload, timeout=30)
    assert r.status_code == 400
