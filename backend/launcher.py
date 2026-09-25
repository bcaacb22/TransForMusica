"""Transformusic launcher — starts the backend and opens the browser."""
import os
import sys
import threading
import time
import webbrowser

# Ensure we can find backend modules regardless of how we're launched
if getattr(sys, 'frozen', False):
    # Running as PyInstaller bundle
    BASE = os.path.dirname(sys.executable)
    os.chdir(BASE)
    sys.path.insert(0, BASE)
    # Point fpcalc at the bundled copy
    fpcalc = os.path.join(BASE, 'fpcalc.exe')
    if os.path.exists(fpcalc):
        os.environ['FPCALC'] = fpcalc
else:
    BASE = os.path.dirname(os.path.abspath(__file__))
    os.chdir(BASE)
    sys.path.insert(0, BASE)

# Load .env from backend/
from dotenv import load_dotenv
load_dotenv(os.path.join(BASE, '.env'))

PORT = int(os.environ.get('RUN_PORT', os.environ.get('PORT', 8001)))

def open_browser():
    time.sleep(2.5)
    webbrowser.open(f'http://localhost:{PORT}')

if __name__ == '__main__':
    threading.Thread(target=open_browser, daemon=True).start()
    import uvicorn
    uvicorn.run('server:app', host='127.0.0.1', port=PORT, log_level='info')
