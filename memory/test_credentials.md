# Test Credentials

No authentication is currently implemented in the app. All endpoints are public.

## Ollama Mock Server (for backend testing only)
A mock Ollama server script is available at `/tmp/mock_ollama.py`.
Start it with: `nohup python /tmp/mock_ollama.py > /tmp/mock_ollama.log 2>&1 &`
It listens on `http://localhost:11434` and returns 2 fake models plus canned lyrics.
Use this when testing Ollama integration from the cloud preview (real Ollama is not reachable).
