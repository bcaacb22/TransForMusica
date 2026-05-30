import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  apiRequest,
  apiPost,
  apiGet,
  apiGetBlob,
  ApiError,
  isRetriable,
  isNetworkError,
  triggerDownload,
} from './apiClient';

describe('apiClient', () => {
  let originalFetch;

  beforeEach(() => {
    originalFetch = global.fetch;
    vi.useFakeTimers();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  describe('isRetriable', () => {
    it('returns true for 5xx status codes', () => {
      expect(isRetriable(500)).toBe(true);
      expect(isRetriable(502)).toBe(true);
      expect(isRetriable(503)).toBe(true);
      expect(isRetriable(599)).toBe(true);
    });

    it('returns true for 429 (rate limited)', () => {
      expect(isRetriable(429)).toBe(true);
    });

    it('returns false for 4xx (non-429)', () => {
      expect(isRetriable(400)).toBe(false);
      expect(isRetriable(401)).toBe(false);
      expect(isRetriable(403)).toBe(false);
      expect(isRetriable(404)).toBe(false);
      expect(isRetriable(422)).toBe(false);
    });

    it('returns false for 2xx', () => {
      expect(isRetriable(200)).toBe(false);
      expect(isRetriable(201)).toBe(false);
    });
  });

  describe('isNetworkError', () => {
    it('returns true for TypeError with fetch message', () => {
      const err = new TypeError('Failed to fetch');
      expect(isNetworkError(err)).toBe(true);
    });

    it('returns false for non-TypeError', () => {
      const err = new Error('Failed to fetch');
      expect(isNetworkError(err)).toBe(false);
    });

    it('returns false for TypeError without fetch message', () => {
      const err = new TypeError('Cannot read property');
      expect(isNetworkError(err)).toBe(false);
    });
  });

  describe('ApiError', () => {
    it('has status and body properties', () => {
      const err = new ApiError(404, 'Not Found');
      expect(err.status).toBe(404);
      expect(err.body).toBe('Not Found');
      expect(err.message).toBe('API Error 404: Not Found');
      expect(err).toBeInstanceOf(Error);
    });
  });

  describe('apiRequest', () => {
    it('returns response on success', async () => {
      const mockResponse = { ok: true, status: 200 };
      global.fetch = vi.fn().mockResolvedValue(mockResponse);

      const res = await apiRequest('/api/test');
      expect(res).toBe(mockResponse);
      expect(global.fetch).toHaveBeenCalledTimes(1);
    });

    it('throws ApiError immediately for 4xx (non-429)', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
        text: () => Promise.resolve('Bad Request'),
      });

      await expect(apiRequest('/api/test', {}, { maxRetries: 3 }))
        .rejects.toThrow(ApiError);

      // Should NOT retry — only 1 fetch call
      expect(global.fetch).toHaveBeenCalledTimes(1);
    });

    it('retries on 5xx and eventually succeeds', async () => {
      const successResponse = { ok: true, status: 200 };
      global.fetch = vi.fn()
        .mockResolvedValueOnce({ ok: false, status: 500, text: () => Promise.resolve('Server Error') })
        .mockResolvedValueOnce(successResponse);

      const promise = apiRequest('/api/test', {}, { maxRetries: 3 });
      await vi.runAllTimersAsync();

      const res = await promise;
      expect(res).toBe(successResponse);
      expect(global.fetch).toHaveBeenCalledTimes(2);
    });

    it('retries on 429 and eventually succeeds', async () => {
      const successResponse = { ok: true, status: 200 };
      global.fetch = vi.fn()
        .mockResolvedValueOnce({ ok: false, status: 429, text: () => Promise.resolve('Rate Limited') })
        .mockResolvedValueOnce(successResponse);

      const promise = apiRequest('/api/test', {}, { maxRetries: 3 });
      await vi.runAllTimersAsync();

      const res = await promise;
      expect(res).toBe(successResponse);
      expect(global.fetch).toHaveBeenCalledTimes(2);
    });

    it('retries on network error and eventually succeeds', async () => {
      const successResponse = { ok: true, status: 200 };
      global.fetch = vi.fn()
        .mockRejectedValueOnce(new TypeError('Failed to fetch'))
        .mockResolvedValueOnce(successResponse);

      const promise = apiRequest('/api/test', {}, { maxRetries: 3 });
      await vi.runAllTimersAsync();

      const res = await promise;
      expect(res).toBe(successResponse);
      expect(global.fetch).toHaveBeenCalledTimes(2);
    });

    it('throws after exhausting all retries on 5xx', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
        text: () => Promise.resolve('Service Unavailable'),
      });

      const promise = apiRequest('/api/test', {}, { maxRetries: 3 });
      // Attach catch handler immediately to prevent unhandled rejection
      const caught = promise.catch(e => e);

      await vi.runAllTimersAsync();

      const error = await caught;
      expect(error).toBeInstanceOf(ApiError);
      expect(error.status).toBe(503);

      // Initial attempt + 3 retries = 4 total calls
      expect(global.fetch).toHaveBeenCalledTimes(4);
    });

    it('throws after exhausting all retries on network error', async () => {
      global.fetch = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'));

      const promise = apiRequest('/api/test', {}, { maxRetries: 3 });
      // Attach catch handler immediately to prevent unhandled rejection
      const caught = promise.catch(e => e);

      await vi.runAllTimersAsync();

      const error = await caught;
      expect(error).toBeInstanceOf(TypeError);
      expect(error.message).toContain('fetch');

      // Initial attempt + 3 retries = 4 total calls
      expect(global.fetch).toHaveBeenCalledTimes(4);
    });

    it('does not retry unknown errors', async () => {
      global.fetch = vi.fn().mockRejectedValue(new Error('Unknown error'));

      await expect(apiRequest('/api/test', {}, { maxRetries: 3 }))
        .rejects.toThrow('Unknown error');

      // Should NOT retry — only 1 fetch call
      expect(global.fetch).toHaveBeenCalledTimes(1);
    });

    it('respects maxRetries option', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
        text: () => Promise.resolve('Error'),
      });

      const promise = apiRequest('/api/test', {}, { maxRetries: 1 });
      const caught = promise.catch(e => e);

      await vi.runAllTimersAsync();

      const error = await caught;
      expect(error).toBeInstanceOf(ApiError);
      expect(error.status).toBe(500);

      // Initial attempt + 1 retry = 2 total calls
      expect(global.fetch).toHaveBeenCalledTimes(2);
    });
  });

  describe('apiPost', () => {
    it('sends JSON body with correct headers', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ success: true }),
      });

      const result = await apiPost('/api/test', { key: 'value' });
      expect(result).toEqual({ success: true });
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/test',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ key: 'value' }),
        })
      );
    });

    it('sends FormData without Content-Type header', async () => {
      const formData = new FormData();
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ uploaded: true }),
      });

      const result = await apiPost('/api/upload', formData);
      expect(result).toEqual({ uploaded: true });
      expect(global.fetch).toHaveBeenCalledWith(
        '/api/upload',
        expect.objectContaining({
          method: 'POST',
          headers: undefined,
          body: formData,
        })
      );
    });
  });

  describe('apiGet', () => {
    it('returns parsed JSON', async () => {
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ data: [1, 2, 3] }),
      });

      const result = await apiGet('/api/items');
      expect(result).toEqual({ data: [1, 2, 3] });
    });
  });

  describe('apiGetBlob', () => {
    it('returns a blob', async () => {
      const mockBlob = new Blob(['audio data'], { type: 'audio/wav' });
      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        blob: () => Promise.resolve(mockBlob),
      });

      const result = await apiGetBlob('/api/download');
      expect(result).toBe(mockBlob);
    });
  });

  describe('triggerDownload', () => {
    it('creates and clicks a download link', () => {
      const mockBlob = new Blob(['test'], { type: 'text/plain' });
      const mockClick = vi.fn();
      const mockCreateElement = vi.spyOn(document, 'createElement').mockReturnValue({
        href: '',
        download: '',
        click: mockClick,
      });
      const mockCreateObjectURL = vi.fn().mockReturnValue('blob:test-url');
      const mockRevokeObjectURL = vi.fn();
      global.URL.createObjectURL = mockCreateObjectURL;
      global.URL.revokeObjectURL = mockRevokeObjectURL;

      triggerDownload(mockBlob, 'test.wav');

      expect(mockCreateObjectURL).toHaveBeenCalledWith(mockBlob);
      expect(mockClick).toHaveBeenCalled();
      expect(mockRevokeObjectURL).toHaveBeenCalledWith('blob:test-url');

      mockCreateElement.mockRestore();
    });
  });
});
