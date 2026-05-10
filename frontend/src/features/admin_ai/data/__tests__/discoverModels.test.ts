/**
 * Tests for the discoverModels API client.
 *
 * What: Verifies the happy path response shape, all 6 error code mappings
 *       (network, 401, 403, 404, 422, 502), and that the auth helper works.
 *
 * Phase/Slice: P00 / P00-S02-T007 — AdminAiModelsPage discover wizard UI
 *
 * Mock strategy:
 *   Direct vi.spyOn(globalThis, 'fetch') per test — no MSW dependency added
 *   (project does not have MSW yet). Each test restores the spy via afterEach.
 *   Per 01-non-negotiables.md §Tests are REAL: the API client's internal
 *   branching is exercised with real code paths, only the HTTP transport is
 *   mocked. The real endpoint is verified in the /verify-slice human gate.
 *
 * Source-of-truth refs:
 *   - task-pack P00-S02-T007.md §12.2 (API client test layer)
 *   - task-pack P00-S02-T007.md §3.3 (error codes)
 *   - task-pack P00-S02-T007.md §7 (A3, A4 acceptance criteria)
 */

import { describe, it, expect, vi, afterEach } from 'vitest';
import { discoverModels } from '../discoverModels';
import { getAdminAuthHeader } from '../auth';
import type { DiscoverModelsResponse } from '../types';

// ── Fixtures ─────────────────────────────────────────────────────────────────

const VALID_PROVIDER_ID = '12345678-1234-4234-8234-123456789abc';

const HAPPY_RESPONSE: DiscoverModelsResponse = {
  data: {
    added: [
      {
        id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
        provider_id: VALID_PROVIDER_ID,
        model_id: 'gemini-1.5-pro',
        model_type: 'chat',
        capabilities: ['chat'],
        enabled: true,
        is_default: false,
        auto_discovered: true,
      },
    ],
    existing: [
      {
        id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
        provider_id: VALID_PROVIDER_ID,
        model_id: 'gemini-1.0-pro',
        model_type: 'chat',
        capabilities: ['chat'],
        enabled: true,
        is_default: false,
        auto_discovered: true,
      },
    ],
    skipped: [
      { model_id: 'unknown-model', reason: 'unsupported_model_type' },
    ],
    total_seen: 3,
  },
};

// ── Helper: create a mock fetch that returns the given response ───────────────

function mockFetch(status: number, body: unknown) {
  return vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as Response);
}

function mockFetchNetworkError(message = 'Network error') {
  return vi.spyOn(globalThis, 'fetch').mockRejectedValueOnce(new Error(message));
}

afterEach(() => {
  vi.restoreAllMocks();
});

// ── Test suites ───────────────────────────────────────────────────────────────

describe('admin_ai / discoverModels API client', () => {
  // ── Happy path ───────────────────────────────────────────────────────────

  it('happy path: returns ok=true with DiscoverModelsData on 200', async () => {
    mockFetch(200, HAPPY_RESPONSE);

    const result = await discoverModels(VALID_PROVIDER_ID);

    expect(result.ok).toBe(true);
    if (!result.ok) return; // narrow type

    expect(result.value.added).toHaveLength(1);
    expect(result.value.added[0].model_id).toBe('gemini-1.5-pro');
    expect(result.value.existing).toHaveLength(1);
    expect(result.value.skipped).toHaveLength(1);
    expect(result.value.skipped[0].reason).toBe('unsupported_model_type');
    expect(result.value.total_seen).toBe(3);
  });

  // ── Error mapping: 401 → unauthorized ────────────────────────────────────

  it('maps 401 to error_code=unauthorized', async () => {
    mockFetch(401, {
      detail: { error: { code: 'require_admin', message: 'Auth required' } },
    });

    const result = await discoverModels(VALID_PROVIDER_ID);

    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.error.code).toBe('unauthorized');
    expect(result.error.httpStatus).toBe(401);
  });

  // ── Error mapping: 403 → forbidden ───────────────────────────────────────

  it('maps 403 to error_code=forbidden', async () => {
    mockFetch(403, {
      detail: { error: { code: 'require_admin', message: 'Forbidden' } },
    });

    const result = await discoverModels(VALID_PROVIDER_ID);

    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.error.code).toBe('forbidden');
    expect(result.error.httpStatus).toBe(403);
  });

  // ── Error mapping: 404 → provider_not_found ──────────────────────────────

  it('maps 404 to error_code=provider_not_found', async () => {
    mockFetch(404, {
      detail: { error: { code: 'provider_not_found', message: 'Not found' } },
    });

    const result = await discoverModels(VALID_PROVIDER_ID);

    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.error.code).toBe('provider_not_found');
    expect(result.error.httpStatus).toBe(404);
  });

  // ── Error mapping: 422 → validation_error ────────────────────────────────

  it('maps 422 to error_code=validation_error', async () => {
    mockFetch(422, {
      detail: { error: { code: 'unsupported_provider', message: 'Unsupported' } },
    });

    const result = await discoverModels(VALID_PROVIDER_ID);

    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.error.code).toBe('validation_error');
    expect(result.error.httpStatus).toBe(422);
  });

  // ── Error mapping: 502 → upstream_error ──────────────────────────────────

  it('maps 502 to error_code=upstream_error', async () => {
    mockFetch(502, {
      detail: { error: { code: 'upstream_provider_error', message: 'Upstream fail' } },
    });

    const result = await discoverModels(VALID_PROVIDER_ID);

    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.error.code).toBe('upstream_error');
    expect(result.error.httpStatus).toBe(502);
  });

  // ── Error mapping: network/transport failure ──────────────────────────────

  it('maps network transport failure to error_code=network_error', async () => {
    mockFetchNetworkError('fetch failed');

    const result = await discoverModels(VALID_PROVIDER_ID);

    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.error.code).toBe('network_error');
    expect(result.error.httpStatus).toBeUndefined();
  });
});

// ── getAdminAuthHeader ───────────────────────────────────────────────────────

describe('admin_ai / getAdminAuthHeader', () => {
  it('returns an object with an Authorization key', () => {
    const header = getAdminAuthHeader();
    expect(header).toHaveProperty('Authorization');
  });

  it('Authorization value starts with "Bearer dev-admin-"', () => {
    const { Authorization } = getAdminAuthHeader();
    expect(Authorization).toMatch(/^Bearer dev-admin-/);
  });

  it('does not expose any production-looking token (no sk-, no AIza*)', () => {
    const { Authorization } = getAdminAuthHeader();
    expect(Authorization).not.toMatch(/sk-|AIza/);
  });
});
