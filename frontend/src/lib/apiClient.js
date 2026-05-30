// src/lib/apiClient.js — Resilient HTTP Client with retry + exponential backoff

import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';
const DEFAULT_MAX_RETRIES = 3;
const BASE_DELAY_MS = 1000;

/**
 * Determines if a given HTTP status code is retriable.
 * 5xx (server errors) and 429 (rate limited) are retriable.
 */
export function isRetriable(status) {
  if (status >= 500 && status <= 599) return true;
  if (status === 429) return true;
  return false;
}

/**
 * Determines if an error is a network-level fetch failure.
 */
export function isNetworkError(error) {
  return error instanceof TypeError && error.message.includes('fetch');
}

/**
 * Returns a promise that resolves after the given number of milliseconds.
 */
export function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Custom error class for API errors, carrying the HTTP status and response body.
 */
export class ApiError extends Error {
  constructor(status, body) {
    super(`API Error ${status}: ${body}`);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

/**
 * Core request function with retry logic and exponential backoff.
 *
 * - Retries up to `maxRetries` times for 5xx, 429, and network errors.
 * - Uses exponential backoff: 1s, 2s, 4s delays between retries.
 * - Surfaces 4xx errors (non-429) immediately without retry.
 *
 * @param {string} path - The API path (will be prefixed with BACKEND_URL)
 * @param {RequestInit} options - Standard fetch options
 * @param {{ maxRetries?: number }} retryOptions - Retry configuration
 * @returns {Promise<Response>} The successful fetch Response
 * @throws {ApiError} On non-retriable HTTP errors or after retries exhausted
 */
export async function apiRequest(path, options = {}, { maxRetries = DEFAULT_MAX_RETRIES } = {}) {
  const url = `${BACKEND_URL}${path}`;
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

      // Retriable status — will retry after backoff
      lastError = new ApiError(res.status, await res.text());
    } catch (err) {
      // If it's a non-retriable ApiError, throw immediately
      if (err instanceof ApiError && !isRetriable(err.status)) throw err;
      // If it's not a network error and not an ApiError, throw immediately
      if (!isNetworkError(err) && !(err instanceof ApiError)) throw err;
      lastError = err;
    }

    if (attempt < maxRetries) {
      const delay = BASE_DELAY_MS * Math.pow(2, attempt); // 1s, 2s, 4s
      await sleep(delay);
    }
  }

  // All retries exhausted — show user-facing error toast
  const errorMessage = lastError instanceof ApiError
    ? `Request failed (${lastError.status}): ${lastError.body}`
    : lastError?.message || 'Network error — please check your connection';
  toast.error(errorMessage);

  throw lastError;
}

/**
 * POST JSON or FormData to the given path.
 * Automatically sets Content-Type for JSON bodies.
 *
 * @param {string} path - The API path
 * @param {object|FormData} body - Request body
 * @returns {Promise<any>} Parsed JSON response
 */
export async function apiPost(path, body) {
  const isForm = body instanceof FormData;
  const res = await apiRequest(path, {
    method: 'POST',
    headers: isForm ? undefined : { 'Content-Type': 'application/json' },
    body: isForm ? body : JSON.stringify(body),
  });
  return res.json();
}

/**
 * GET JSON from the given path.
 *
 * @param {string} path - The API path
 * @returns {Promise<any>} Parsed JSON response
 */
export async function apiGet(path) {
  const res = await apiRequest(path);
  return res.json();
}

/**
 * GET a Blob from the given path (for file downloads).
 *
 * @param {string} path - The API path
 * @returns {Promise<Blob>} The response as a Blob
 */
export async function apiGetBlob(path) {
  const res = await apiRequest(path);
  return res.blob();
}

/**
 * Triggers a browser download for the given blob with the specified filename.
 *
 * @param {Blob} blob - The file content
 * @param {string} filename - The download filename
 */
export function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
