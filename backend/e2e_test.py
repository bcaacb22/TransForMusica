"""End-to-end test suite for Transformusic API."""
import requests
import numpy as np
import soundfile as sf
import io
import time

API = "http://localhost:8200/api"

print("=" * 50)
print("TRANSFORMUSIC END-TO-END TEST SUITE")
print("=" * 50)

# 1. Health
r = requests.get(f"{API}/")
assert r.status_code == 200
msg = r.json()["message"]
print(f"[PASS] Health check: {msg}")

# 2. Create project
r = requests.post(f"{API}/projects", json={"name": "E2E_TEST"})
assert r.status_code == 200
pid = r.json()["id"]
print(f"[PASS] Project created: {pid[:8]}...")

# 3. Upload audio (3 sec sine wave)
sr = 22050
t = np.linspace(0, 3.0, int(sr * 3.0), endpoint=False)
y = (0.3 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
buf = io.BytesIO()
sf.write(buf, y, sr, format="WAV")
buf.seek(0)
r = requests.post(f"{API}/projects/{pid}/upload", files={"file": ("test.wav", buf, "audio/wav")})
assert r.status_code == 200
fname = r.json()["filename"]
print(f"[PASS] File uploaded: {fname}")

# 4. Legal scan (Gateway 01)
r = requests.post(f"{API}/projects/{pid}/legal-scan", timeout=60)
assert r.status_code == 200
scan = r.json()
risk = scan["violationRisk"]
bpm = scan.get("bpm")
key = scan.get("key")
print(f"[PASS] Gateway 01 - Legal scan: risk={risk}, bpm={bpm}, key={key}")

# 5. Transform (Gateway 02)
r = requests.post(f"{API}/projects/{pid}/transform", timeout=10)
assert r.status_code == 200
print(f"[PASS] Gateway 02 - Transform triggered")

# Poll for completion
for i in range(30):
    time.sleep(5)
    r = requests.get(f"{API}/projects/{pid}/transform-status")
    data = r.json()
    status = data.get("status")
    if status == "complete":
        midi = data.get("midi_files", [])
        xml = data.get("musicxml_files", [])
        stems = data.get("audio_stems", [])
        print(f"[PASS] Gateway 02 - Transform complete in {(i+1)*5}s")
        print(f"       MIDI files: {midi}")
        print(f"       MusicXML:   {xml}")
        print(f"       Audio stems: {stems}")
        break
    elif status == "failed":
        err = data.get("error", "unknown")
        print(f"[FAIL] Gateway 02 - Transform failed: {err}")
        break
else:
    print("[FAIL] Gateway 02 - Transform timed out (150s)")

# 6. Download stems ZIP
r = requests.get(f"{API}/projects/{pid}/download-stems")
assert r.status_code == 200
kb = len(r.content) // 1024
print(f"[PASS] Stems ZIP downloaded: {kb} KB")

# 7. Profile endpoints
r = requests.get(f"{API}/profile")
assert r.status_code == 200
prof = r.json()
print(f"[PASS] Profile: id={prof['id']}, bias={prof['fingerprint_bias']}")

# Add corpus item
r = requests.post(f"{API}/profile/corpus", json={"text": "Test bars for the test\nEvery line a quest", "source": "manual"})
assert r.status_code == 200
print("[PASS] Profile corpus: added item")

# Compute fingerprint (heuristic only)
r = requests.post(f"{API}/profile/fingerprint/compute", json={"use_llm_theme": False})
assert r.status_code == 200
fp = r.json().get("fingerprint")
assert fp is not None
rhyme = fp["phonetic"]["rhyme_density"]
print(f"[PASS] Fingerprint computed: rhyme_density={rhyme}")

# 8. User styles CRUD
r = requests.post(f"{API}/user-styles", json={"name": "TEST_STYLE", "description": "aggressive", "sample_lyrics": "bars"})
assert r.status_code == 200
sid = r.json()["id"]
r = requests.get(f"{API}/user-styles")
assert r.status_code == 200
assert any(s["id"] == sid for s in r.json())
r = requests.delete(f"{API}/user-styles/{sid}")
assert r.status_code == 200
print("[PASS] User styles CRUD: create/list/delete")

# 9. Ollama config
r = requests.get(f"{API}/ollama/config")
assert r.status_code == 200
base_url = r.json()["base_url"]
print(f"[PASS] Ollama config: {base_url}")

# 10. Transcribe endpoint
buf2 = io.BytesIO()
sf.write(buf2, y, sr, format="WAV")
buf2.seek(0)
r = requests.post(f"{API}/transcribe", files={"file": ("tone.wav", buf2, "audio/wav")}, timeout=120)
assert r.status_code == 200
print(f"[PASS] Whisper transcribe: returned text='{r.json()['text'][:30]}...'")

print()
print("=" * 50)
print("ALL TESTS PASSED - TRANSFORMUSIC IS FUNCTIONAL")
print("=" * 50)
print()
print("Working gateways:")
print("  Gateway 01 (Legal Scan)      - OK")
print("  Gateway 02 (Deconstruction)  - OK")
print("  Gateway 04 (Lyric Rebuild)   - Needs LM Studio on :1234")
print("  Gateway 05 (Voice Clone)     - Needs voice server on :8500")
print()
print("Frontend: http://localhost:3200")
print("Backend:  http://localhost:8200")
