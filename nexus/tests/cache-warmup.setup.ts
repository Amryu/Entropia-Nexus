import { test as setup, expect } from '@playwright/test';

/**
 * Pre-warm the exchange cache before parallel tests run.
 *
 * The first request to /api/market/exchange triggers a full cache build
 * (22+ parallel API endpoint fetches + categorization + Brotli/Gzip compression)
 * which can take 10-30s. If multiple workers hit this simultaneously, the API
 * server gets overwhelmed and drops connections (ECONNRESET).
 *
 * By warming the cache in a setup project, all subsequent worker requests
 * are served from the pre-built cache.
 */
setup('warm exchange cache', async ({ request }) => {
  setup.setTimeout(120_000);

  const response = await request.get('/api/market/exchange');
  expect(response.ok()).toBe(true);
});
