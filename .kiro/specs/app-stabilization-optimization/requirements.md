# Requirements Document

## Introduction

This specification covers the stabilization and optimization of the Transformusic application. The scope includes: stabilizing all live gateways (01 Legal Diagnostic, 02 Deconstruction, 04 Lyric Rebuild), bringing Gateway 05 (Voice Clone) to a fully tested end-to-end state, removing legacy build tooling (react-scripts/craco) in favor of Vite + Vitest, decomposing the monolithic App.jsx into per-gateway components, fixing async/sync mismatches in the backend, and implementing robust error handling with exponential backoff retries.

## Glossary

- **Backend**: The FastAPI Python 3.11 server (`server.py`) serving all API endpoints on port 8200
- **Frontend**: The React 19 single-page application built with Vite, Tailwind CSS, and shadcn/ui
- **Gateway**: A discrete processing stage in the Transformusic pipeline (Legal Diagnostic, Deconstruction, Morph Engine, Lyric Rebuild, Voice Clone)
- **Build_Toolchain**: The set of tools used to bundle, serve, and test the frontend application
- **Voice_Clone_Server**: The external F5-TTS or XTTS server running on port 8500 that performs text-to-speech voice cloning
- **Style_Engine**: The Python module (`style_engine.py`) that computes lyric fingerprints using heuristic analysis and optional LLM interpretation
- **Retry_Handler**: A client-side mechanism that automatically retries failed API requests with exponential backoff before surfacing errors to the user
- **Error_Boundary**: A React component that catches JavaScript errors in its child component tree and renders a fallback UI
- **Async_Handler**: A backend request handler that uses non-blocking I/O via Python asyncio
- **Blocking_Call**: A synchronous function invocation that halts the event loop when called inside an async context
- **Backpressure**: A flow-control mechanism that limits the number of concurrent background tasks to prevent resource exhaustion

## Requirements

### Requirement 1: Remove Legacy Build Tooling

**User Story:** As a developer, I want the frontend to use a single consistent build and test toolchain, so that builds are predictable and the test script works.

#### Acceptance Criteria

1. THE Build_Toolchain SHALL use Vite as the sole bundler for development serving and production builds.
2. THE Build_Toolchain SHALL use Vitest as the sole test runner for frontend unit and integration tests.
3. WHEN the `npm run test` or `yarn test` script is executed, THE Build_Toolchain SHALL invoke Vitest in run mode.
4. THE Build_Toolchain SHALL have no dependency on react-scripts in package.json dependencies or devDependencies.
5. THE Build_Toolchain SHALL have no dependency on @craco/craco in package.json dependencies or devDependencies.
6. WHEN the `npm run build` or `yarn build` script is executed, THE Build_Toolchain SHALL produce a production bundle via Vite without errors.
7. THE Frontend SHALL remove the `craco.config.js` file from the project.

### Requirement 2: Decompose Monolithic Frontend

**User Story:** As a developer, I want the 2000-line App.jsx split into per-gateway components, so that each gateway is independently maintainable and testable.

#### Acceptance Criteria

1. THE Frontend SHALL provide a dedicated component file for Gateway 01 (Legal Diagnostic).
2. THE Frontend SHALL provide a dedicated component file for Gateway 02 (Deconstruction).
3. THE Frontend SHALL provide a dedicated component file for Gateway 04 (Lyric Rebuild).
4. THE Frontend SHALL provide a dedicated component file for Gateway 05 (Voice Clone).
5. THE Frontend SHALL provide a root App component that composes the gateway components and manages navigation between views (Home, Studio, Settings).
6. WHEN a gateway component is rendered, THE Frontend SHALL encapsulate all state and logic specific to that gateway within the gateway component.
7. THE Frontend SHALL maintain the existing visual appearance and user interaction flow after decomposition.

### Requirement 3: Frontend Error Boundaries

**User Story:** As a user, I want the application to gracefully handle rendering errors in any gateway, so that a failure in one gateway does not crash the entire application.

#### Acceptance Criteria

1. THE Frontend SHALL wrap each gateway component in an Error_Boundary.
2. WHEN a JavaScript error occurs within a gateway component, THE Error_Boundary SHALL render a fallback UI indicating the error and offering a retry action.
3. WHEN an Error_Boundary catches an error, THE Error_Boundary SHALL log the error details to the browser console.
4. WHEN an Error_Boundary catches an error, THE Frontend SHALL keep all other gateway components operational.

### Requirement 4: API Retry with Exponential Backoff

**User Story:** As a user, I want transient API failures to be retried automatically, so that I do not see errors caused by momentary network or server issues.

#### Acceptance Criteria

1. WHEN an API request fails with a network error or a 5xx status code, THE Retry_Handler SHALL retry the request up to 3 attempts before surfacing the error to the user.
2. THE Retry_Handler SHALL use exponential backoff with a base delay of 1 second between retry attempts (1s, 2s, 4s).
3. WHEN all retry attempts are exhausted, THE Retry_Handler SHALL display a user-facing error notification describing the failure.
4. THE Retry_Handler SHALL apply to all gateway API calls (legal-scan, transform, generate-lyrics, voice-clone).
5. IF a request receives a 4xx status code (excluding 429), THEN THE Retry_Handler SHALL surface the error immediately without retrying.
6. WHEN a request receives a 429 (rate-limited) status code, THE Retry_Handler SHALL retry using the same exponential backoff strategy.

### Requirement 5: Fix Backend Async/Sync Mismatches

**User Story:** As a developer, I want all blocking operations in async handlers to be properly offloaded, so that the event loop is never blocked and concurrent requests are handled efficiently.

#### Acceptance Criteria

1. WHEN the Backend performs MIDI conversion via Basic Pitch, THE Backend SHALL execute the conversion in a thread pool using `asyncio.to_thread`.
2. WHEN the Backend performs Demucs stem separation locally, THE Backend SHALL execute the separation in a thread pool using `asyncio.to_thread`.
3. WHEN the Backend calls Style_Engine functions (heuristic_fingerprint, build_learned_style_prompt), THE Backend SHALL execute those calls in a thread pool using `asyncio.to_thread`.
4. WHEN the Backend calls the local Whisper model for transcription, THE Backend SHALL execute the transcription in a thread pool using `asyncio.to_thread`.
5. THE Backend SHALL limit concurrent background tasks spawned via `asyncio.create_task` to a maximum of 10 simultaneous tasks using a semaphore-based Backpressure mechanism.

### Requirement 6: Stabilize Gateway 01 (Legal Diagnostic)

**User Story:** As a user, I want the Legal Diagnostic gateway to reliably scan my uploaded audio and report results, so that I can assess copyright risk before proceeding.

#### Acceptance Criteria

1. WHEN a project has an uploaded audio file, THE Backend SHALL perform the AuDD.io fingerprint scan and return a structured result containing violation_risk, matched source, BPM, and key.
2. IF the AuDD.io API is unreachable or returns an error, THEN THE Backend SHALL return a response with violation_risk set to "UNKNOWN" and include the error description.
3. IF no AuDD API key is configured, THEN THE Backend SHALL return a response indicating the scan is unavailable rather than throwing an unhandled exception.
4. WHEN the legal scan completes, THE Frontend SHALL display the scan results including violation risk level, matched source (if any), BPM, and detected key.

### Requirement 7: Stabilize Gateway 02 (Deconstruction)

**User Story:** As a user, I want the Deconstruction gateway to reliably separate stems and produce MIDI/MusicXML files, so that I can download and use them in my DAW.

#### Acceptance Criteria

1. WHEN a transform is triggered, THE Backend SHALL separate the audio into stems (drums, bass, vocals, other) and convert each stem to MIDI and MusicXML.
2. WHEN the transform completes successfully, THE Backend SHALL return a response containing the list of MIDI files, MusicXML files, and a flag indicating stems are available.
3. IF the remote Demucs server is unreachable, THEN THE Backend SHALL fall back to local CPU-based Demucs separation.
4. IF stem separation fails entirely, THEN THE Backend SHALL return a structured error response with status code 500 and a descriptive error message.
5. WHEN the user requests a stems download, THE Backend SHALL return a ZIP archive containing all MIDI files, MusicXML files, and the transformation guide.

### Requirement 8: Stabilize Gateway 04 (Lyric Rebuild)

**User Story:** As a user, I want the Lyric Rebuild gateway to generate lyrics reliably across all modes (preset, defined, learned, blend, custom), so that I always receive usable output or a clear error.

#### Acceptance Criteria

1. WHEN lyrics are requested in "learned" mode with an empty corpus, THE Backend SHALL return HTTP 400 with a message indicating the corpus is empty.
2. WHEN lyrics are requested in "defined" mode without a user_style_id, THE Backend SHALL return HTTP 400 with a message indicating the style ID is required.
3. IF the LLM server is unreachable, THEN THE Backend SHALL return HTTP 503 with a message indicating the LLM service is unavailable.
4. WHEN lyrics are generated successfully, THE Backend SHALL persist the lyrics to the project document in MongoDB.
5. WHEN lyrics are generated in "learned" mode, THE Backend SHALL append the generated lyrics to the profile corpus with source "generated".

### Requirement 9: Bring Gateway 05 (Voice Clone) End-to-End

**User Story:** As a user, I want to upload a voice sample and clone my voice onto generated lyrics, so that I can hear my lyrics performed in a specific voice.

#### Acceptance Criteria

1. WHEN a voice sample is uploaded via the voice-sample endpoint, THE Backend SHALL store the audio file and associate it with the project.
2. WHEN a voice clone is triggered, THE Backend SHALL send the voice sample and lyrics text to the Voice_Clone_Server and initiate synthesis.
3. WHEN the Voice_Clone_Server returns a synthesized audio file, THE Backend SHALL store the result and update the project voice_clone_status to "complete".
4. IF the Voice_Clone_Server is unreachable, THEN THE Backend SHALL return HTTP 503 with a message indicating the voice clone service is unavailable.
5. IF the Voice_Clone_Server returns an error, THEN THE Backend SHALL update the project voice_clone_status to "failed" and return the error details.
6. WHEN the voice clone status is "complete", THE Backend SHALL serve the cloned vocal audio file via the download-vocal endpoint.
7. THE Frontend SHALL provide a UI for Gateway 05 that allows the user to upload a voice reference, trigger cloning, view progress status, and download the result.
8. WHEN the voice clone is in progress, THE Frontend SHALL poll the voice-clone-status endpoint and display the current status to the user.

### Requirement 10: Backend Task Backpressure

**User Story:** As a developer, I want background tasks to be bounded, so that the server does not exhaust memory or CPU under concurrent load.

#### Acceptance Criteria

1. THE Backend SHALL maintain a global asyncio.Semaphore with a limit of 10 concurrent background tasks.
2. WHEN a new background task is created via `asyncio.create_task`, THE Backend SHALL acquire the semaphore before executing the task body.
3. WHEN a background task completes or fails, THE Backend SHALL release the semaphore.
4. IF the semaphore is fully acquired and a new task is requested, THEN THE Backend SHALL queue the task until a slot becomes available rather than rejecting the request.

### Requirement 11: Frontend Test Infrastructure

**User Story:** As a developer, I want a working test setup with Vitest, so that I can write and run unit tests for gateway components.

#### Acceptance Criteria

1. THE Build_Toolchain SHALL include a Vitest configuration file compatible with the existing Vite config and path aliases.
2. THE Build_Toolchain SHALL include jsdom or happy-dom as the test environment for component testing.
3. WHEN `yarn test` is executed, THE Build_Toolchain SHALL discover and run test files matching `**/*.test.{js,jsx,ts,tsx}` or `**/*.spec.{js,jsx,ts,tsx}`.
4. THE Build_Toolchain SHALL include at least one smoke test per gateway component verifying it renders without errors.
