#!/usr/bin/env python3
"""
live_mongo_check.py

Create a project by POSTing to a running backend HTTP API and verify the created
project is persisted in MongoDB using pymongo.

This script talks to the backend over HTTP (no in-process import) and then
connects to MongoDB to verify persistence.

Usage:
    python backend/live_mongo_check.py [--backend BACKEND_URL] [--mongo MONGO_URL]
                                       [--db DB_NAME] [--name PROJECT_NAME]
                                       [--cleanup] [--timeout SECS]

Examples:
    # Basic, using defaults
    python backend/live_mongo_check.py

    # Specify backend and mongo URLs
    python backend/live_mongo_check.py --backend http://127.0.0.1:8000 --mongo mongodb://127.0.0.1:27017 --db beat_maker

Notes:
- Exits with code 0 on success (document found in Mongo).
- Non-zero exit codes indicate different failure points.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, Optional

try:
    import requests
except Exception:
    print("ERROR: `requests` package is required. Install with `pip install requests`.", file=sys.stderr)
    sys.exit(1)

try:
    from pymongo import MongoClient
    from pymongo.errors import PyMongoError
except Exception:
    print("ERROR: `pymongo` package is required. Install with `pip install pymongo`.", file=sys.stderr)
    sys.exit(1)


EXIT_OK = 0
EXIT_HTTP_FAIL = 2
EXIT_MONGO_CONNECT_FAIL = 3
EXIT_NOT_FOUND = 4
EXIT_EXCEPTION = 5


def pretty(obj: Any) -> str:
    try:
        return json.dumps(obj, indent=2, default=str)
    except Exception:
        return str(obj)


def create_project_via_api(backend_url: str, project_name: str, timeout: float = 10.0) -> Dict[str, Any]:
    url = backend_url.rstrip("/") + "/api/projects"
    payload = {"name": project_name}
    resp = requests.post(url, json=payload, timeout=timeout)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"API returned HTTP {resp.status_code}: {resp.text}")
    try:
        return resp.json()
    except Exception as e:
        raise RuntimeError(f"Could not decode JSON from API response: {e}. Raw: {resp.text}")


def find_project_in_mongo(mongo_url: str, db_name: str, project_id: str, retries: int = 10, delay: float = 0.5) -> Optional[Dict[str, Any]]:
    """
    Connect to Mongo and look for a document with id == project_id in the projects collection.
    Retries a few times to allow the backend to finish async persistence.
    """
    try:
        client = MongoClient(mongo_url, serverSelectionTimeoutMS=3000)
        # quick ping
        client.admin.command("ping")
    except PyMongoError as e:
        raise ConnectionError(f"Could not connect/ping MongoDB at {mongo_url}: {e}")

    db = client[db_name]
    coll = db.get_collection("projects")

    for attempt in range(1, retries + 1):
        doc = coll.find_one({"id": project_id})
        if doc:
            # convert ObjectId and other non-serializable types to strings
            normalized = {}
            for k, v in doc.items():
                try:
                    json.dumps(v, default=str)
                    normalized[k] = v
                except Exception:
                    normalized[k] = str(v)
            return normalized
        if attempt < retries:
            time.sleep(delay)
    return None


def delete_project_in_mongo(mongo_url: str, db_name: str, project_id: str) -> bool:
    try:
        client = MongoClient(mongo_url, serverSelectionTimeoutMS=3000)
        client.admin.command("ping")
        db = client[db_name]
        res = db.projects.delete_one({"id": project_id})
        return res.deleted_count > 0
    except Exception:
        return False


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Create a project via backend API and verify persistence in MongoDB.")
    p.add_argument("--backend", "-b", default=os.environ.get("BACKEND_URL", "http://127.0.0.1:8000"),
                   help="Base URL of the backend (default: http://127.0.0.1:8000)")
    p.add_argument("--mongo", "-m", default=os.environ.get("MONGO_URL", "mongodb://127.0.0.1:27017"),
                   help="MongoDB connection URL (default: mongodb://127.0.0.1:27017)")
    p.add_argument("--db", "-d", default=os.environ.get("DB_NAME", "beat_maker"),
                   help="MongoDB database name (default: beat_maker)")
    p.add_argument("--name", "-n", default=None,
                   help="Project name to create. If omitted, a timestamped name will be generated.")
    p.add_argument("--cleanup", action="store_true", help="Delete the test project from MongoDB at the end (best-effort).")
    p.add_argument("--retries", type=int, default=10, help="How many times to poll Mongo for the document (default: 10).")
    p.add_argument("--delay", type=float, default=0.5, help="Seconds between Mongo polling attempts (default: 0.5s).")
    p.add_argument("--timeout", type=float, default=10.0, help="HTTP request timeout in seconds (default: 10).")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    backend_url = args.backend
    mongo_url = args.mongo
    db_name = args.db
    project_name = args.name or f"live-check-{int(time.time())}"

    print(f"Backend URL: {backend_url}")
    print(f"Mongo URL: {mongo_url}")
    print(f"DB name: {db_name}")
    print(f"Project name: {project_name}")

    try:
        print("\n-> Creating project via backend API...")
        created = create_project_via_api(backend_url, project_name, timeout=args.timeout)
        print("API response:")
        print(pretty(created))
    except Exception as e:
        print(f"\nERROR creating project via API: {e}", file=sys.stderr)
        return EXIT_HTTP_FAIL

    project_id = created.get("id")
    if not project_id:
        print("\nERROR: API response did not include an 'id' field.", file=sys.stderr)
        return EXIT_HTTP_FAIL

    try:
        print(f"\n-> Verifying persistence in MongoDB (polling up to {args.retries} times)...")
        doc = find_project_in_mongo(mongo_url, db_name, project_id, retries=args.retries, delay=args.delay)
    except ConnectionError as e:
        print(f"\nERROR connecting to MongoDB: {e}", file=sys.stderr)
        return EXIT_MONGO_CONNECT_FAIL
    except Exception as e:
        print(f"\nUnexpected error while checking MongoDB: {e}", file=sys.stderr)
        return EXIT_EXCEPTION

    if not doc:
        print(f"\nERROR: Project with id {project_id} was not found in MongoDB after polling.", file=sys.stderr)
        return EXIT_NOT_FOUND

    print("\nSUCCESS: Found project document in MongoDB:")
    print(pretty(doc))

    if args.cleanup:
        try:
            deleted = delete_project_in_mongo(mongo_url, db_name, project_id)
            print("\nCleanup: delete returned:", deleted)
        except Exception as e:
            print("\nCleanup: error while deleting project (ignored):", e)

    return EXIT_OK


if __name__ == "__main__":
    try:
        rc = main()
    except Exception as exc:
        print("Unhandled exception:", exc, file=sys.stderr)
        rc = EXIT_EXCEPTION
    sys.exit(rc)
