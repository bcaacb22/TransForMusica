# Design Document

## Overview

This design covers the stabilization and optimization of the Transformusic application: decomposing the monolithic frontend, adding resilience patterns (retry, error boundaries, backpressure), removing legacy build tooling, fixing async mismatches, and bringing Gateway 05 (Voice Clone) to a fully tested end-to-end state.

## Architecture

This design decomposes the Transformusic application into maintainable modules across both frontend and backend, introduces resilience patterns (retry, error boundaries, backpressure), removes legacy tooling, and brings Gateway 05 (Voice Clone) to a fully tested state.

The architecture follows three principles:
1. **Separation by gateway** — each gateway is an independent unit with its own component, state, and API interactions
2. **Resilience at the boundary** — all external calls (APIs, LLM, voice clone server) go through retry/error handling layers
3. **Bounded concurrency** — background tasks are semaphore-gated to prevent resource exhaustion

```
┌─────────────────────────────────────────────────────────────────┐
│  Frontend (React 19 + Vite)                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │Gateway01 │ │Gateway02 │ │Gateway04 │ │Gateway05 │          │
│  │  Legal   │ │  Decon   │ │  Lyric   │ │  Voice   │          │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘          │
│       │             │             │             │               │
│  ┌────▼─────────────▼─────────────▼─────────────▼──────┐       │
│  │              apiClient (retry + backoff)             │       │
│  └─────────────────────────┬───────────────────────────┘       │
│                            │                                    │
│  ┌─────────────────────────▼───────────────────────────┐       │
│  │           ErrorBoundary (per gateway)                │       │
│  └─────────────────────────────────────────────────────┘       │
└────────────────────────────────┬────────────────────────────────┘
                                 │ HTTP (Vite proxy /api → :8200)
┌────────────────────────────────▼────────────────────────────────┐
│  Backend (FastAPI + uvicorn)                                     │
│  ┌──────────────────────────────────────────────────────┐       │
│  │  TaskManager (semaphore-gated asyncio.create_task)   │       │
│  └──────────────────────────────────────────────────────┘       │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐          │
│  │ legal    │ │transform │ │ lyrics   │ │  voice   │          │
│  │ scan     │ │ pipeline │ │ generate │ │  clone   │          │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘          │
│       │             │             │             │               │
│  External:    Demucs GPU    LM Studio/     Voice Clone          │
│  AuDD.io     (fallback CPU) Ollama :1234   Server :8500        │
└─────────────────────────────────────────────────────────────────┘
```

---

## Components and Interfaces

### Frontend Components

#### 1. `src/lib/apiClient.js` — Resilient HTTP Client

A thin wrapper around `fetch` that adds retry logic with exponential backoff.

```javascript
// src/lib/apiClient.js

const DEFAULT_MAX_RETRIES = 3;
const BASE_DELAY_MS = 1000;

function isRetriable(status) {
  if (status >= 500 && status <= 599) return true;
  if (status === 429) return true;
  return false;
}

function isNetworkError(error) {
  return error instanceof TypeError && error.message.includes('fetch');
}

async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

export async function apiRequest(path, options = {}, { maxRetries = DEFAULT_MAX_RETRIES } = {}) {
  const url = `${path}`;
  let lastError;

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const res = await fetch(url, options);

      if (res.ok) return res;

      if (!isRetriable(res.status)) {
        // 4xx (non-429) — surface immediately
        const text = await res.text();
        throw new ApiError(res.status, text);
      }

      // Retriable status — will retry
      lastError = new ApiError(res.status, await res.text());
    } catch (err) {
      if (err instanceof ApiError && !isRetriable(err.status)) throw err;
      if (!isNetworkError(err) && err instanceof ApiError === false) throw err;
      lastError = err;
    }

    if (attempt < maxRetries) {
      const delay = BASE_DELAY_MS * Math.pow(2, attempt); // 1s, 2s, 4s
      await sleep(delay);
    }
  }

  throw lastError;
}

export class ApiError extends Error {
  constructor(status, body) {
    super(`API Error ${status}: ${body}`);
    this.status = status;
    this.body = body;
  }
}

export async function apiPost(path, body) {
  const isForm = body instanceof FormData;
  const res = await apiRequest(path, {
    method: 'POST',
    headers: isForm ? undefined : { 'Content-Type': 'application/json' },
    body: isForm ? body : JSON.stringify(body),
  });
  return res.json();
}

export async function apiGet(path) {
  const res = await apiRequest(path);
  return res.json();
}

export async function apiGetBlob(path) {
  const res = await apiRequest(path);
  return res.blob();
}
```

#### 2. `src/components/ErrorBoundary.jsx` — Gateway Error Isolation

```javascript
// src/components/ErrorBoundary.jsx
import { Component } from 'react';

export class GatewayErrorBoundary extends Component {
  state = { hasError: false, error: null };

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, errorInfo) {
    console.error(`[ErrorBoundary] Gateway error:`, error, errorInfo);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div role="alert" className="error-boundary-fallback">
          <p>Something went wrong in this gateway.</p>
          <p className="error-detail">{this.state.error?.message}</p>
          <button onClick={this.handleRetry}>Retry</button>
        </div>
      );
    }
    return this.props.children;
  }
}
```

#### 3. Gateway Components

Each gateway is extracted from the monolithic `App.jsx` into its own file:

| File | Responsibility |
|------|---------------|
| `src/components/gateways/Gateway01Legal.jsx` | Legal diagnostic scan UI, results display |
| `src/components/gateways/Gateway02Deconstruction.jsx` | Stem separation progress, download controls |
| `src/components/gateways/Gateway04LyricRebuild.jsx` | Style selection, lyrics generation, display |
| `src/components/gateways/Gateway05VoiceClone.jsx` | Voice sample upload, clone trigger, status polling, download |

Each gateway component:
- Receives `projectId` and `project` data as props
- Manages its own local state (useState/useRef)
- Uses `apiClient` for all backend calls
- Is wrapped in a `GatewayErrorBoundary` by the parent App

#### 4. `src/App.jsx` — Slim Root Orchestrator

The refactored App.jsx (~200-300 lines) handles:
- View navigation (Home / Studio / Settings)
- Project selection and creation
- Gateway state machine progression
- Composing gateway components with error boundaries

```javascript
// src/App.jsx (simplified structure)
import { GatewayErrorBoundary } from './components/ErrorBoundary';
import Gateway01Legal from './components/gateways/Gateway01Legal';
import Gateway02Deconstruction from './components/gateways/Gateway02Deconstruction';
import Gateway04LyricRebuild from './components/gateways/Gateway04LyricRebuild';
import Gateway05VoiceClone from './components/gateways/Gateway05VoiceClone';

function StudioView({ project, state, onAdvance }) {
  return (
    <>
      {state === 'gateway_01' && (
        <GatewayErrorBoundary>
          <Gateway01Legal projectId={project.id} project={project} onComplete={onAdvance} />
        </GatewayErrorBoundary>
      )}
      {state === 'gateway_02' && (
        <GatewayErrorBoundary>
          <Gateway02Deconstruction projectId={project.id} project={project} onComplete={onAdvance} />
        </GatewayErrorBoundary>
      )}
      {state === 'gateway_04' && (
        <GatewayErrorBoundary>
          <Gateway04LyricRebuild projectId={project.id} project={project} onComplete={onAdvance} />
        </GatewayErrorBoundary>
      )}
      {state === 'gateway_05' && (
        <GatewayErrorBoundary>
          <Gateway05VoiceClone projectId={project.id} project={project} onComplete={onAdvance} />
        </GatewayErrorBoundary>
      )}
    </>
  );
}
```

#### 5. `src/components/gateways/Gateway05VoiceClone.jsx` — New Gateway

```javascript
// src/components/gateways/Gateway05VoiceClone.jsx
import { useState, useEffect, useRef, useCallback } from 'react';
import { apiPost, apiGet, apiGetBlob } from '../../lib/apiClient';

export default function Gateway05VoiceClone({ projectId, project, onComplete }) {
  const [voiceProfile, setVoiceProfile] = useState(null);
  const [cloneStatus, setCloneStatus] = useState('idle'); // idle | processing | complete | failed
  const [error, setError] = useState(null);
  const pollRef = useRef(null);

  const handleUploadSample = async (file) => {
    const form = new FormData();
    form.append('file', file);
    await apiPost(`/api/projects/${projectId}/voice-sample`, form);
    setVoiceProfile({ name: file.name.toUpperCase(), file });
  };

  const handleTriggerClone = async () => {
    setCloneStatus('processing');
    setError(null);
    await apiPost(`/api/projects/${projectId}/voice-clone`, {});
    startPolling();
  };

  const startPolling = useCallback(() => {
    pollRef.current = setInterval(async () => {
      const result = await apiGet(`/api/projects/${projectId}/voice-clone-status`);
      if (result.status === 'complete') {
        setCloneStatus('complete');
        clearInterval(pollRef.current);
      } else if (result.status === 'failed') {
        setCloneStatus('failed');
        setError(result.error);
        clearInterval(pollRef.current);
      }
    }, 3000);
  }, [projectId]);

  useEffect(() => {
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, []);

  const handleDownload = async () => {
    const blob = await apiGetBlob(`/api/projects/${projectId}/download-vocal`);
    triggerDownload(blob, 'CLONED_VOCAL.wav');
  };

  // ... render UI with upload, trigger, status, download
}
```

---

### Backend Components

#### 6. `backend/task_manager.py` — Semaphore-Gated Task Runner

```python
# backend/task_manager.py
import asyncio
import logging

logger = logging.getLogger(__name__)

_semaphore: asyncio.Semaphore | None = None
MAX_CONCURRENT_TASKS = 10


def get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
    return _semaphore


async def create_bounded_task(coro, *, name: str = ""):
    """Wrap a coroutine in semaphore acquisition before executing."""
    sem = get_semaphore()

    async def _guarded():
        async with sem:
            logger.info(f"Task started: {name}")
            try:
                return await coro
            except Exception as e:
                logger.error(f"Task failed: {name} — {e}")
                raise
            finally:
                logger.info(f"Task slot released: {name}")

    return asyncio.create_task(_guarded(), name=name)
```

Usage in `server.py`:
```python
from task_manager import create_bounded_task

# Replace: asyncio.create_task(_run_transform(...))
# With:
await create_bounded_task(_run_transform(project_id, str(original_path)), name=f"transform-{project_id}")
```

#### 7. Async Fixes in `server.py`

The `extract_stems_and_convert_to_midi` function is already called via `run_in_executor` in `_run_transform`. The remaining blocking calls that need wrapping:

```python
# In generate_lyrics endpoint — style_engine calls:
fingerprint = await asyncio.to_thread(heuristic_fingerprint, profile['corpus'])
samples = await asyncio.to_thread(select_representative_samples, profile['corpus'], 3)
prompt = await asyncio.to_thread(
    build_learned_style_prompt, user_brief, fingerprint, samples, llm_theme, bias
)

# In legal_scan — librosa analysis:
y, sr = await asyncio.to_thread(librosa.load, str(file_path), sr=None, mono=True, duration=60)
```

#### 8. Gateway 05 Backend — Voice Clone Error Handling

The existing `_run_voice_clone` already handles success/failure state transitions. The missing piece is proper HTTP 503 when the server is unreachable at trigger time:

```python
@api_router.post("/projects/{project_id}/voice-clone")
async def start_voice_clone(project_id: str, body: VoiceCloneRequest = VoiceCloneRequest()):
    # ... existing validation ...

    # Pre-check voice clone server availability
    if VOICE_CLONE_URL:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                await client.get(f"{VOICE_CLONE_URL}/health")
        except (httpx.ConnectError, httpx.TimeoutException):
            raise HTTPException(
                status_code=503,
                detail="Voice clone service is unavailable. Ensure the server is running on port 8500."
            )

    await db.projects.update_one(
        {"id": project_id},
        {"$set": {"voice_clone_status": "processing", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    await create_bounded_task(_run_voice_clone(project_id), name=f"voice-clone-{project_id}")
    return {"status": "processing"}
```

---

## Interfaces

### API Client Interface (Frontend)

```typescript
// Type definitions for the apiClient module
interface ApiRequestOptions {
  maxRetries?: number;  // default: 3
}

function apiRequest(path: string, fetchOptions?: RequestInit, retryOptions?: ApiRequestOptions): Promise<Response>;
function apiPost(path: string, body: object | FormData): Promise<any>;
function apiGet(path: string): Promise<any>;
function apiGetBlob(path: string): Promise<Blob>;

class ApiError extends Error {
  status: number;
  body: string;
}
```

### TaskManager Interface (Backend)

```python
async def create_bounded_task(coro: Coroutine, *, name: str = "") -> asyncio.Task:
    """Submit a coroutine to run under the global semaphore.
    
    - Acquires semaphore before executing
    - Releases semaphore on completion or failure
    - Queues if all 10 slots are occupied (does not reject)
    """
    ...

def get_semaphore() -> asyncio.Semaphore:
    """Return the global semaphore (lazily initialized, limit=10)."""
    ...
```

### Gateway Component Props Interface

```typescript
interface GatewayProps {
  projectId: string;
  project: Project;
  onComplete: () => void;
}

interface Project {
  id: string;
  name: string;
  original_file?: string;
  lyrics?: string;
  voice_sample_file?: string;
  voice_clone_status?: 'pending' | 'processing' | 'complete' | 'failed';
  transform_status?: 'pending' | 'processing' | 'complete' | 'failed';
  legal_scan?: LegalScanResult;
}
```

---

## Data Models

No new MongoDB collections are introduced. The existing `projects` collection gains these fields (already partially present):

| Field | Type | Added By |
|-------|------|----------|
| `voice_sample_file` | string | Gateway 05 upload |
| `voice_clone_status` | enum: pending/processing/complete/failed | Gateway 05 state |
| `voice_clone_file` | string | Gateway 05 completion |
| `voice_clone_error` | string | Gateway 05 failure |
| `transform_status` | enum: pending/processing/complete/failed | Gateway 02 state |
| `transform_error` | string | Gateway 02 failure |

---

## Error Handling

### Frontend Error Layers

1. **Error Boundary (render errors)** — catches React render exceptions per gateway, shows fallback UI with retry
2. **API Client (network/server errors)** — retries 5xx and 429 with exponential backoff (1s, 2s, 4s), surfaces 4xx immediately
3. **Toast notifications** — after retries exhausted, displays user-facing error via sonner toast

### Backend Error Layers

1. **Input validation** — Pydantic models + explicit HTTPException(400) for bad requests
2. **External service errors** — catch `httpx.ConnectError`/`TimeoutException`, return 503 with descriptive message
3. **Background task failures** — update project status to "failed" with error details in DB
4. **Startup recovery** — reset orphaned "processing" jobs to "pending" on server restart

### Retry Decision Matrix

| Status Code | Retry? | Reason |
|-------------|--------|--------|
| 2xx | No | Success |
| 400-428 | No | Client error, retrying won't help |
| 429 | Yes | Rate limited, backoff will help |
| 430-499 | No | Client error |
| 500-599 | Yes | Server error, may be transient |
| Network error | Yes | Connection may recover |

---

## Build Toolchain Changes

### Removals
- `react-scripts` from dependencies
- `@craco/craco` from devDependencies
- `craco.config.js` file
- `cra-template` from dependencies

### Additions
- `vitest` as devDependency
- `@testing-library/react` as devDependency
- `@testing-library/jest-dom` as devDependency
- `jsdom` as devDependency (test environment)
- `vitest.config.js` or inline in `vite.config.js`

### Updated Scripts
```json
{
  "scripts": {
    "start": "vite",
    "build": "vite build",
    "test": "vitest --run",
    "test:watch": "vitest"
  }
}
```

### Vitest Configuration

```javascript
// vitest.config.js
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react({ include: /\.(jsx|js)$/ })],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['**/*.{test,spec}.{js,jsx,ts,tsx}'],
    setupFiles: ['./src/test-setup.js'],
  },
});
```

---

## Testing Strategy

### Unit Tests (Vitest + Testing Library)
- Smoke tests for each gateway component (renders without error)
- API client retry logic with mocked fetch
- Error boundary behavior with intentionally-throwing components
- TaskManager semaphore behavior with concurrent coroutines

### Property-Based Tests (Vitest + fast-check)
- Retry handler: for random sequences of status codes, verify correct retry/no-retry behavior
- Exponential backoff: for any retry attempt index, verify correct delay calculation
- Backpressure: for any number of concurrent tasks, verify at most 10 execute simultaneously

### Integration Tests
- Backend endpoints with mocked external services (AuDD, LLM, Voice Clone)
- Full gateway flows: upload → process → poll → download

---

## Correctness Properties

*A property is a characteristic or behavior that should hold true across all valid executions of a system — essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.*

### Property 1: Error boundary isolates gateway failures

*For any* gateway component that throws a JavaScript error during rendering, the Error Boundary SHALL catch the error, render a fallback UI containing the error message and a retry action, while all sibling gateway components continue to render normally.

**Validates: Requirements 3.1, 3.2, 3.4**

### Property 2: Error boundary logs caught errors

*For any* error caught by a GatewayErrorBoundary, the boundary SHALL call `console.error` with the error object and component stack information.

**Validates: Requirements 3.3**

### Property 3: Retriable errors are retried with bounded attempts

*For any* API request that fails with a 5xx status code, a 429 status code, or a network error, the Retry Handler SHALL retry the request exactly 3 additional times before surfacing the error to the caller.

**Validates: Requirements 4.1, 4.3, 4.6**

### Property 4: Exponential backoff timing

*For any* retry sequence triggered by a retriable error, the delay between attempt N and attempt N+1 SHALL be `1000 * 2^N` milliseconds (producing delays of 1s, 2s, 4s for attempts 0, 1, 2).

**Validates: Requirements 4.2**

### Property 5: Non-retriable errors surface immediately

*For any* API response with a 4xx status code where the code is not 429, the Retry Handler SHALL throw the error immediately without any retry attempts.

**Validates: Requirements 4.5**

### Property 6: Backpressure semaphore bounds concurrency

*For any* set of N background tasks submitted via `create_bounded_task`, at most 10 tasks SHALL be executing concurrently at any point in time, and all N tasks SHALL eventually complete (none are rejected).

**Validates: Requirements 5.5, 10.1, 10.2, 10.3, 10.4**

### Property 7: AuDD error produces UNKNOWN violation risk

*For any* error condition from the AuDD.io API (connection refused, timeout, HTTP error, API error response), the legal scan endpoint SHALL return a result with `violation_risk` set to `"UNKNOWN"` and a non-empty error description.

**Validates: Requirements 6.2**

### Property 8: Successful transform returns complete result structure

*For any* successful execution of `extract_stems_and_convert_to_midi`, the returned dictionary SHALL contain keys `stem_midis` (list), `musicxml_files` (list), `main_midi` (string), and `success` set to `true`.

**Validates: Requirements 7.2**

### Property 9: Failed transform returns structured error

*For any* exception raised during stem separation or MIDI conversion, the function SHALL return a dictionary with `success` set to `false` and an `error` key containing a non-empty string description.

**Validates: Requirements 7.4**

### Property 10: Generated lyrics are persisted to project

*For any* successfully generated lyrics string, reading the project document from MongoDB immediately after generation SHALL return a `lyrics` field equal to the generated string.

**Validates: Requirements 8.4**

### Property 11: Learned mode appends to profile corpus

*For any* lyrics generated in "learned" mode, the profile corpus SHALL contain a new entry with `source` equal to `"generated"` and `text` equal to the generated lyrics.

**Validates: Requirements 8.5**

### Property 12: Voice sample upload associates with project

*For any* audio file uploaded via the voice-sample endpoint, the project document SHALL contain a `voice_sample_file` field referencing the stored file, and that file SHALL exist on disk.

**Validates: Requirements 9.1**

### Property 13: Voice clone status transitions are consistent

*For any* voice clone operation, if the Voice Clone Server returns a successful audio file then `voice_clone_status` SHALL be `"complete"` and `voice_clone_file` SHALL reference an existing file; if the server returns an error then `voice_clone_status` SHALL be `"failed"` and `voice_clone_error` SHALL contain a non-empty description.

**Validates: Requirements 9.3, 9.5**
