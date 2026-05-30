#!/usr/bin/env python3
"""
mongo_integration_test.py

Script to import backend.server (with .env), create a project via TestClient,
and verify it's persisted in MongoDB via pymongo.

Usage:
    cd <repo_root>/app
    python backend/mongo_integration_test.py

The script:
- Loads environment variables from app/backend/.env (if present)
- Imports backend.server robustly (package import first, fallback to file load)
- Calls POST /api/projects to create a test project
- Connects to MongoDB via pymongo and verifies the created document exists in the
  configured database's `projects` collection.

Exit codes:
 - 0: success (document found in Mongo)
 - 1: failure (HTTP failure, missing env, pymongo missing, or document not found)
"""

from __future__ import annotations

import json
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

# Load dotenv from backend directory if present
try:
    from dotenv import load_dotenv
except Exception:
    load_dotenv = None  # will continue; env must be set externally

BACKEND_DIR = Path(__file__).resolve().parent
ENV_PATH = BACKEND_DIR / ".env"
if load_dotenv is not None and ENV_PATH.exists():
    load_dotenv(ENV_PATH)

# Ensure MONGO_URL and DB_NAME are set
MONGO_URL = os.environ.get("MONGO_URL", "")
DB_NAME = os.environ.get("DB_NAME", "")
if not MONGO_URL:
    print("ERROR: MONGO_URL is not set in environment or .env. Aborting.")
    sys.exit(1)
if not DB_NAME:
    print("ERROR: DB_NAME is not set in environment or .env. Aborting.")
    sys.exit(1)

# Import the FastAPI app from backend.server
backend_server = None
try:
    # Try normal package import first
    import importlib

    backend_server = importlib.import_module("backend.server")
except Exception:
    # Fallback: load by file path
    try:
        import importlib.util

        server_path = BACKEND_DIR / "server.py"
        if not server_path.exists():
            raise FileNotFoundError(f"backend/server.py not found at expected path: {server_path}")
        spec = importlib.util.spec_from_file_location("backend.server", str(server_path))
        backend_server = importlib.util.module_from_spec(spec)
        sys.modules["backend.server"] = backend_server
        spec.loader.exec_module(backend_server)  # type: ignore
    except Exception:
        print("ERROR: Could not import backend.server via package or file path.")
        traceback.print_exc()
        sys.exit(1)

if not hasattr(backend_server, "app"):
    print("ERROR: backend.server does not expose 'app'")
    sys.exit(1)

# Use TestClient to create a project
try:
    from fastapi.testclient import TestClient
except Exception:
    print("ERROR: fastapi.testclient is not available. Ensure fastapi is installed.")
    sys.exit(1)

app = getattr(backend_server, "app")
client = TestClient(app)

test_name = f"mongo-integration-test-{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}"
print(f"Creating project with name: {test_name}")

try:
    resp = client.post("/api/projects", json={"name": test_name}, timeout=30)
except Exception:
    print("ERROR: Exception while calling POST /api/projects:")
    traceback.print_exc()
    sys.exit(1)

if resp.status_code not in (200, 201):
    print(f"ERROR: POST /api/projects returned status {resp.status_code}")
    try:
        print("Response body:", resp.json())
    except Exception:
        print("Response text:", resp.text)
    sys.exit(1)

try:
    created = resp.json()
except Exception:
    print("ERROR: Could not decode JSON response from POST /api/projects")
    print("Raw response text:", resp.text)
    sys.exit(1)

proj_id = created.get("id")
if not proj_id:
    print("ERROR: Created project JSON did not contain 'id':", json.dumps(created, indent=2))
    sys.exit(1)

print(f"Project created with id: {proj_id}")
print("Now verifying persistence in MongoDB...")

# Connect to MongoDB via pymongo and verify document exists
try:
    from pymongo import MongoClient
except Exception:
    print("ERROR: pymongo is not installed. Install pymongo to run this integration test.")
    sys.exit(1)

client_mongo = None
try:
    client_mongo = MongoClient(MONGO_URL, serverSelectionTimeoutMS=3000)
    # quick ping
    client_mongo.admin.command("ping")
except Exception:
    print("ERROR: Could not connect/ping MongoDB using MONGO_URL:", MONGO_URL)
    traceback.print_exc()
    sys.exit(1)

db = client_mongo[DB_NAME]
projects_coll = db.get_collection("projects")

# Retry loop: allow a small window for eventual consistency
found_doc = None
retries = 10
for attempt in range(retries):
    found_doc = projects_coll.find_one({"id": proj_id})
    if found_doc:
        break
    time.sleep(0.3)

if not found_doc:
    print(f"ERROR: Created project with id {proj_id} not found in MongoDB collection '{DB_NAME}.projects'.")
    print("Collection sample (first 5 docs):")
    try:
        sample = list(projects_coll.find().limit(5))
        print(json.dumps(sample, default=str, indent=2))
    except Exception:
        print("Could not list documents from collection; check Mongo permissions.")
    sys.exit(1)

# Success: print the found document
print("SUCCESS: Project document persisted in MongoDB.")
# Remove the ObjectId from output or convert it to string
def _normalize(doc: Dict[str, Any]) -> Dict[str, Any]:
    out = {}
    for k, v in doc.items():
        try:
            # attempt to JSON-serialize common Mongo types
            if hasattr(v, "isoformat"):
                out[k] = v.isoformat()
            else:
                out[k] = str(v) if (not isinstance(v, (str, int, float, bool, type(None), dict, list))) else v
        except Exception:
            out[k] = str(v)
    return out

try:
    printable = _normalize(found_doc)
    print(json.dumps(printable, indent=2, default=str))
except Exception:
    print("Document (raw):", found_doc)

# Optionally: clean up the test document from DB (uncomment if desired)
# projects_coll.delete_one({"id": proj_id})

sys.exit(0)
