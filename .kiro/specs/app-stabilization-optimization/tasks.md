# Implementation Plan: App Stabilization & Optimization

## Overview

This plan implements the Transformusic stabilization in four phases: (1) build tooling so tests work, (2) backend fixes for a stable foundation, (3) frontend decomposition using the new patterns, and (4) Gateway 05 integration that depends on everything else being stable. Each task is independently verifiable and preserves existing functionality.

## Tasks

- [x] 1. Remove legacy build tooling and set up test infrastructure
  - [x] 1.1 Remove legacy dependencies and update package.json scripts
    - Remove `react-scripts`, `cra-template`, and `@craco/craco` from package.json
    - Add `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `jsdom`, and `fast-check` as devDependencies
    - Update scripts: `"test": "vitest --run"`, `"test:watch": "vitest"`
    - Delete `craco.config.js`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.7_

  - [x] 1.2 Create Vitest configuration and test setup
    - Create `vitest.config.js` with jsdom environment, globals enabled, and `@` path alias
    - Create `src/test-setup.js` importing `@testing-library/jest-dom`
    - Verify `yarn test` discovers and runs test files matching `**/*.{test,spec}.{js,jsx}`
    - _Requirements: 11.1, 11.2, 11.3_

  - [x] 1.3 Verify build still works
    - Run `yarn build` and confirm Vite produces a production bundle without errors
    - _Requirements: 1.6_

- [x] 2. Checkpoint — Build tooling verified
  - Ensure `yarn test` and `yarn build` both pass, ask the user if questions arise.

- [x] 3. Backend resilience: TaskManager and async fixes
  - [x] 3.1 Implement TaskManager with semaphore-gated concurrency
    - Create `backend/task_manager.py` with `get_semaphore()` and `create_bounded_task()` functions
    - Global semaphore limit of 10 concurrent tasks
    - Logging on task start, failure, and slot release
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

  - [x] 3.2 Replace bare `asyncio.create_task` calls in server.py with `create_bounded_task`
    - Update `_run_transform` task creation to use `create_bounded_task`
    - Update `_run_voice_clone` task creation to use `create_bounded_task`
    - _Requirements: 5.5, 10.2_

  - [x] 3.3 Wrap blocking calls in `asyncio.to_thread`
    - Wrap `heuristic_fingerprint`, `select_representative_samples`, and `build_learned_style_prompt` calls in `generate_lyrics` endpoint
    - Wrap `librosa.load` in the legal scan endpoint
    - Wrap any remaining synchronous Basic Pitch / Demucs calls in `_run_transform`
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [ ]* 3.4 Write unit tests for TaskManager semaphore behavior
    - Test that at most 10 tasks execute concurrently when 20 are submitted
    - Test that all submitted tasks eventually complete (none rejected)
    - Test that semaphore is released on task failure
    - _Requirements: 10.1, 10.2, 10.3, 10.4_

- [x] 4. Backend gateway stabilization
  - [x] 4.1 Stabilize Gateway 01 (Legal Diagnostic) error handling
    - Ensure AuDD.io connection errors return `violation_risk: "UNKNOWN"` with error description
    - Ensure missing API key returns a clear "scan unavailable" response (not unhandled exception)
    - _Requirements: 6.1, 6.2, 6.3_

  - [x] 4.2 Stabilize Gateway 02 (Deconstruction) error handling
    - Ensure remote Demucs failure falls back to local CPU separation
    - Ensure total failure returns structured error with status 500
    - Verify successful transform returns `stem_midis`, `musicxml_files`, `main_midi`, `success: true`
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [x] 4.3 Stabilize Gateway 04 (Lyric Rebuild) validation
    - Return HTTP 400 for learned mode with empty corpus
    - Return HTTP 400 for defined mode without user_style_id
    - Return HTTP 503 when LLM server is unreachable
    - Persist generated lyrics to project document
    - Append generated lyrics to profile corpus in learned mode
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [x] 4.4 Add Gateway 05 (Voice Clone) server availability check
    - Add pre-check to `/voice-clone` endpoint: ping Voice Clone Server health endpoint
    - Return HTTP 503 with descriptive message if server is unreachable
    - Ensure voice clone failure updates project status to "failed" with error details
    - _Requirements: 9.2, 9.4, 9.5_

  - [ ]* 4.5 Write backend integration tests for gateway error paths
    - Test AuDD.io unreachable → UNKNOWN violation_risk
    - Test LLM unreachable → 503
    - Test Voice Clone server unreachable → 503
    - Test transform failure → structured error response
    - _Requirements: 6.2, 7.4, 8.3, 9.4_

- [x] 5. Checkpoint — Backend stable
  - Ensure all backend tests pass, ask the user if questions arise.

- [x] 6. Frontend: API client and error boundary
  - [x] 6.1 Create resilient API client module
    - Create `src/lib/apiClient.js` with `apiRequest`, `apiPost`, `apiGet`, `apiGetBlob` functions
    - Implement retry logic: 3 retries for 5xx, 429, and network errors
    - Implement exponential backoff: 1s, 2s, 4s delays
    - Surface 4xx (non-429) errors immediately without retry
    - Export `ApiError` class with status and body
    - _Requirements: 4.1, 4.2, 4.5, 4.6_

  - [x] 6.2 Create GatewayErrorBoundary component
    - Create `src/components/ErrorBoundary.jsx` with fallback UI showing error message and retry button
    - Log caught errors to console with component stack info
    - Reset error state on retry click
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [ ]* 6.3 Write property tests for API client retry logic
    - **Property 3: Retriable errors are retried with bounded attempts**
    - **Property 4: Exponential backoff timing**
    - **Property 5: Non-retriable errors surface immediately**
    - **Validates: Requirements 4.1, 4.2, 4.5, 4.6**

  - [ ]* 6.4 Write property test for error boundary isolation
    - **Property 1: Error boundary isolates gateway failures**
    - **Property 2: Error boundary logs caught errors**
    - **Validates: Requirements 3.1, 3.2, 3.3, 3.4**

- [x] 7. Frontend: Decompose App.jsx into gateway components
  - [x] 7.1 Extract Gateway01Legal component
    - Create `src/components/gateways/Gateway01Legal.jsx`
    - Move all legal scan state, handlers, and UI from App.jsx into this component
    - Accept `projectId`, `project`, and `onComplete` props
    - Use `apiClient` for all API calls (replace raw fetch/axios)
    - Preserve existing visual appearance exactly
    - _Requirements: 2.1, 2.6, 2.7, 6.4_

  - [x] 7.2 Extract Gateway02Deconstruction component
    - Create `src/components/gateways/Gateway02Deconstruction.jsx`
    - Move all transform/stem separation state, handlers, and UI from App.jsx
    - Accept `projectId`, `project`, and `onComplete` props
    - Use `apiClient` for all API calls
    - Preserve existing visual appearance exactly
    - _Requirements: 2.2, 2.6, 2.7, 7.5_

  - [x] 7.3 Extract Gateway04LyricRebuild component
    - Create `src/components/gateways/Gateway04LyricRebuild.jsx`
    - Move all lyric generation state, handlers, and UI from App.jsx
    - Accept `projectId`, `project`, and `onComplete` props
    - Use `apiClient` for all API calls
    - Preserve existing visual appearance exactly
    - _Requirements: 2.3, 2.6, 2.7_

  - [x] 7.4 Create Gateway05VoiceClone component
    - Create `src/components/gateways/Gateway05VoiceClone.jsx`
    - Implement voice sample upload, clone trigger, status polling (3s interval), and download
    - Accept `projectId`, `project`, and `onComplete` props
    - Use `apiClient` for all API calls
    - Handle all states: idle, processing, complete, failed
    - Clean up polling interval on unmount
    - _Requirements: 2.4, 9.1, 9.7, 9.8_

  - [x] 7.5 Refactor App.jsx to compose gateway components
    - Replace inline gateway code with imported gateway components
    - Wrap each gateway in `<GatewayErrorBoundary>`
    - Keep navigation (Home/Studio/Settings), project selection, and state machine in App.jsx
    - Target ~200-300 lines for the refactored App.jsx
    - Preserve existing visual appearance and interaction flow exactly
    - _Requirements: 2.5, 2.7, 3.1, 3.4_

  - [ ]* 7.6 Write smoke tests for each gateway component
    - Test Gateway01Legal renders without errors
    - Test Gateway02Deconstruction renders without errors
    - Test Gateway04LyricRebuild renders without errors
    - Test Gateway05VoiceClone renders without errors
    - _Requirements: 11.4_

- [x] 8. Checkpoint — Frontend decomposition complete
  - Ensure `yarn test` and `yarn build` both pass, visual appearance is unchanged, ask the user if questions arise.

- [x] 9. Gateway 05 end-to-end integration
  - [x] 9.1 Wire Gateway 05 backend endpoints with bounded tasks
    - Ensure `/voice-sample` stores file and associates with project
    - Ensure `/voice-clone` uses `create_bounded_task` for the clone operation
    - Ensure `/voice-clone-status` returns current status from project document
    - Ensure `/download-vocal` serves the cloned audio file when status is "complete"
    - _Requirements: 9.1, 9.2, 9.3, 9.6_

  - [x] 9.2 Add toast notifications for exhausted retries in frontend
    - After all retry attempts fail, display a sonner toast with the error description
    - Apply to all gateway API calls via the apiClient
    - _Requirements: 4.3, 4.4_

  - [ ]* 9.3 Write property tests for Gateway 05 state transitions
    - **Property 12: Voice sample upload associates with project**
    - **Property 13: Voice clone status transitions are consistent**
    - **Validates: Requirements 9.1, 9.3, 9.5**

  - [ ]* 9.4 Write property test for backpressure semaphore
    - **Property 6: Backpressure semaphore bounds concurrency**
    - **Validates: Requirements 5.5, 10.1, 10.2, 10.3, 10.4**

- [x] 10. Final checkpoint — All systems verified
  - Ensure all tests pass (`yarn test` in frontend, `pytest` in backend), ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Gateway 03 (Morph Engine) is explicitly NOT in scope — left as mock/UI-only
- Frontend decomposition preserves existing visual appearance exactly (no style changes)
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["1.3"] },
    { "id": 3, "tasks": ["3.1", "6.1", "6.2"] },
    { "id": 4, "tasks": ["3.2", "3.3", "3.4", "6.3", "6.4"] },
    { "id": 5, "tasks": ["4.1", "4.2", "4.3", "4.4"] },
    { "id": 6, "tasks": ["4.5", "7.1", "7.2", "7.3", "7.4"] },
    { "id": 7, "tasks": ["7.5"] },
    { "id": 8, "tasks": ["7.6"] },
    { "id": 9, "tasks": ["9.1", "9.2"] },
    { "id": 10, "tasks": ["9.3", "9.4"] }
  ]
}
```
