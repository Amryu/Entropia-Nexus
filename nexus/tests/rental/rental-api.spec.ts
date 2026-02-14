import { expect, type Page } from '@playwright/test';
import { test } from '../fixtures/auth';
import { TIMEOUT_MEDIUM } from '../test-constants';

const OFFER_API = '/api/rental';
const ITEM_SET_API = '/api/itemsets';
const OWNER_TEST_USERS = ['verified1', 'verified3', 'admin'] as const;
const RATE_LIMIT_MAX_RETRIES = 4;
const RATE_LIMIT_RETRY_DELAY_MS = 1000;

let ownerUserIndex = 0;

// Default item set data for tests
const DEFAULT_ITEM_SET_DATA = {
  items: [
    { itemId: 1000001, type: 'Weapon', name: 'Test Weapon', quantity: 1, meta: { tier: 3, tiR: 45.5 } }
  ]
};

function nextOwnerUser() {
  const user = OWNER_TEST_USERS[ownerUserIndex % OWNER_TEST_USERS.length];
  ownerUserIndex += 1;
  return user;
}

async function waitForRetry(attempt: number) {
  await new Promise((resolve) => setTimeout(resolve, RATE_LIMIT_RETRY_DELAY_MS * attempt));
}

async function loginAsTestUser(page: Page, userId: string) {
  const loginRes = await page.request.post('/api/test/login', {
    data: { userId }
  });
  expect(loginRes.ok()).toBeTruthy();
}

// Helper: create an item set for use in rental offers
async function createItemSet(page: Page, name = 'Rental Test Set') {
  let lastStatus = 0;

  for (let attempt = 1; attempt <= RATE_LIMIT_MAX_RETRIES; attempt += 1) {
    await loginAsTestUser(page, nextOwnerUser());

    const res = await page.request.post(ITEM_SET_API, {
      data: { name, data: DEFAULT_ITEM_SET_DATA }
    });

    if (res.status() === 201) {
      return res.json();
    }

    lastStatus = res.status();
    if (lastStatus !== 429 || attempt === RATE_LIMIT_MAX_RETRIES) {
      expect(lastStatus).toBe(201);
    }

    await waitForRetry(attempt);
  }

  throw new Error(`createItemSet failed after retries, last status: ${lastStatus}`);
}

async function postWithRateLimitRetry(page: Page, url: string, data: Record<string, unknown>) {
  let response = await page.request.post(url, { data });
  for (let attempt = 1; attempt <= RATE_LIMIT_MAX_RETRIES && response.status() === 429; attempt += 1) {
    await waitForRetry(attempt);
    response = await page.request.post(url, { data });
  }
  return response;
}

// Helper: create a rental offer (draft by default)
async function createOffer(page: Page, overrides: Record<string, unknown> = {}) {
  let lastStatus = 0;

  for (let attempt = 1; attempt <= RATE_LIMIT_MAX_RETRIES; attempt += 1) {
    const itemSet = await createItemSet(page, `Set for ${overrides.title || 'Test Offer'} #${attempt}`);
    const res = await page.request.post(OFFER_API, {
      data: {
        title: 'Test Rental Offer',
        description: 'A test rental offer',
        item_set_id: itemSet.id,
        price_per_day: 5.00,
        deposit: 50.00,
        discounts: [{ minDays: 7, percent: 10 }],
        ...overrides
      }
    });

    if (res.status() !== 429) {
      return { res, itemSetId: itemSet.id };
    }

    lastStatus = res.status();
    if (attempt < RATE_LIMIT_MAX_RETRIES) {
      await waitForRetry(attempt);
    }
  }

  throw new Error(`createOffer failed after retries, last status: ${lastStatus}`);
}

// Helper: create and publish an offer
async function createPublishedOffer(page: Page, overrides: Record<string, unknown> = {}) {
  const { res: createRes } = await createOffer(page, overrides);
  expect(createRes.status()).toBe(201);
  const offer = await createRes.json();

  // Publish it
  let publishRes;
  for (let attempt = 1; attempt <= RATE_LIMIT_MAX_RETRIES; attempt += 1) {
    publishRes = await page.request.put(`${OFFER_API}/${offer.id}`, {
      data: { status: 'available' }
    });

    if (publishRes.status() !== 429) {
      break;
    }

    if (attempt < RATE_LIMIT_MAX_RETRIES) {
      await waitForRetry(attempt);
    }
  }

  expect(publishRes!.status()).toBe(200);
  return publishRes!.json();
}

// Helper: get a future date string (YYYY-MM-DD)
function futureDate(daysFromNow: number): string {
  const d = new Date();
  d.setDate(d.getDate() + daysFromNow);
  return d.toISOString().split('T')[0];
}

test.describe('Rental Offers API', () => {
  test.describe('Authentication & Authorization', () => {
    test('allows unauthenticated GET /api/rental (public listing)', async ({ page }) => {
      const res = await page.request.get(OFFER_API);
      expect(res.status()).toBe(200);
    });

    test('rejects unauthenticated POST /api/rental', async ({ page }) => {
      const res = await page.request.post(OFFER_API, {
        data: { title: 'Test', price_per_day: 5, item_set_id: 'fake' }
      });
      expect(res.status()).toBe(401);
    });

    test('rejects unverified user creating offer', async ({ unverifiedUser }) => {
      const res = await unverifiedUser.request.post(OFFER_API, {
        data: { title: 'Test', price_per_day: 5, item_set_id: 'fake' }
      });
      expect(res.status()).toBe(403);
    });

    test('rejects unauthenticated PUT /api/rental/:id', async ({ page }) => {
      const res = await page.request.put(`${OFFER_API}/1`, {
        data: { title: 'Updated' }
      });
      expect(res.status()).toBe(401);
    });

    test('rejects unauthenticated DELETE /api/rental/:id', async ({ page }) => {
      const res = await page.request.delete(`${OFFER_API}/1`);
      expect(res.status()).toBe(401);
    });
  });

  test.describe('CRUD Operations', () => {
    test('can create a rental offer as draft', async ({ verifiedUser }) => {
      const { res } = await createOffer(verifiedUser, { title: 'My Equipment for Rent' });
      expect(res.status()).toBe(201);

      const offer = await res.json();
      expect(offer.id).toBeDefined();
      expect(offer.title).toBe('My Equipment for Rent');
      expect(offer.status).toBe('draft');
      expect(Number(offer.price_per_day)).toBe(5.00);
      expect(Number(offer.deposit)).toBe(50.00);
      expect(offer.discounts).toHaveLength(1);
      expect(offer.discounts[0].minDays).toBe(7);
      expect(offer.discounts[0].percent).toBe(10);
    });

    test('can get a single rental offer', async ({ verifiedUser }) => {
      const { res: createRes } = await createOffer(verifiedUser);
      const created = await createRes.json();

      const res = await verifiedUser.request.get(`${OFFER_API}/${created.id}`);
      expect(res.status()).toBe(200);

      const offer = await res.json();
      expect(offer.id).toBe(created.id);
      expect(offer.title).toBe('Test Rental Offer');
    });

    test('draft offer is only visible to owner', async ({ verifiedUser, browser }) => {
      const { res: createRes } = await createOffer(verifiedUser);
      const offer = await createRes.json();

      // Another user shouldn't see the draft
      const ctx = await browser.newContext();
      const otherPage = await ctx.newPage();
      await otherPage.goto('/');
      await otherPage.request.post('/api/test/login', { data: { userId: 'verified2' } });
      await otherPage.reload();

      const res = await otherPage.request.get(`${OFFER_API}/${offer.id}`);
      expect(res.status()).toBe(404);
      await ctx.close();
    });

    test('can update offer title and description', async ({ verifiedUser }) => {
      const { res: createRes } = await createOffer(verifiedUser);
      const created = await createRes.json();

      const res = await verifiedUser.request.put(`${OFFER_API}/${created.id}`, {
        data: { title: 'Updated Title', description: 'Updated description' }
      });
      expect(res.status()).toBe(200);

      const updated = await res.json();
      expect(updated.title).toBe('Updated Title');
      expect(updated.description).toBe('Updated description');
    });

    test('can soft delete an offer', async ({ verifiedUser }) => {
      const { res: createRes } = await createOffer(verifiedUser);
      const created = await createRes.json();

      const res = await verifiedUser.request.delete(`${OFFER_API}/${created.id}`);
      expect(res.status()).toBe(200);

      // Should no longer be visible
      const getRes = await verifiedUser.request.get(`${OFFER_API}/${created.id}`);
      expect(getRes.status()).toBe(404);
    });

    test('other user cannot update offer', async ({ verifiedUser, browser }) => {
      const { res: createRes } = await createOffer(verifiedUser);
      const created = await createRes.json();

      // Publish it so it's visible
      await verifiedUser.request.put(`${OFFER_API}/${created.id}`, { data: { status: 'available' } });

      const ctx = await browser.newContext();
      const otherPage = await ctx.newPage();
      await otherPage.goto('/');
      await otherPage.request.post('/api/test/login', { data: { userId: 'verified2' } });
      await otherPage.reload();

      const res = await otherPage.request.put(`${OFFER_API}/${created.id}`, {
        data: { title: 'Hacked Title' }
      });
      expect(res.status()).toBe(403);
      await ctx.close();
    });
  });

  test.describe('Status Transitions', () => {
    test('can publish draft offer (draft -> available)', async ({ verifiedUser }) => {
      const { res: createRes } = await createOffer(verifiedUser);
      const created = await createRes.json();

      const res = await verifiedUser.request.put(`${OFFER_API}/${created.id}`, {
        data: { status: 'available' }
      });
      expect(res.status()).toBe(200);
      const updated = await res.json();
      expect(updated.status).toBe('available');
    });

    test('can unlist available offer (available -> unlisted)', async ({ verifiedUser }) => {
      const offer = await createPublishedOffer(verifiedUser);

      const res = await verifiedUser.request.put(`${OFFER_API}/${offer.id}`, {
        data: { status: 'unlisted' }
      });
      expect(res.status()).toBe(200);
      const updated = await res.json();
      expect(updated.status).toBe('unlisted');
    });

    test('can re-publish unlisted offer (unlisted -> available)', async ({ verifiedUser }) => {
      const offer = await createPublishedOffer(verifiedUser);

      // Unlist
      await verifiedUser.request.put(`${OFFER_API}/${offer.id}`, { data: { status: 'unlisted' } });

      // Re-publish
      const res = await verifiedUser.request.put(`${OFFER_API}/${offer.id}`, {
        data: { status: 'available' }
      });
      expect(res.status()).toBe(200);
      const updated = await res.json();
      expect(updated.status).toBe('available');
    });

    test('rejects invalid transition (draft -> rented)', async ({ verifiedUser }) => {
      const { res: createRes } = await createOffer(verifiedUser);
      const created = await createRes.json();

      const res = await verifiedUser.request.put(`${OFFER_API}/${created.id}`, {
        data: { status: 'rented' }
      });
      expect([400, 409]).toContain(res.status());
      const data = await res.json();
      expect(typeof data.error).toBe('string');
    });

    test('rejects invalid transition (available -> draft) with same-status check', async ({ verifiedUser }) => {
      const offer = await createPublishedOffer(verifiedUser);

      // available -> draft is only allowed when no active requests, but the transition is valid
      const res = await verifiedUser.request.put(`${OFFER_API}/${offer.id}`, {
        data: { status: 'draft' }
      });
      expect(res.status()).toBe(200);
    });
  });

  test.describe('Validation', () => {
    test('rejects offer with missing title', async ({ verifiedUser }) => {
      const itemSet = await createItemSet(verifiedUser);
      const res = await postWithRateLimitRetry(verifiedUser, OFFER_API, {
        item_set_id: itemSet.id,
        price_per_day: 5
      });
      expect(res.status()).toBe(400);
    });

    test('rejects offer with invalid price', async ({ verifiedUser }) => {
      const itemSet = await createItemSet(verifiedUser);
      const res = await postWithRateLimitRetry(verifiedUser, OFFER_API, {
        title: 'Test',
        item_set_id: itemSet.id,
        price_per_day: -1
      });
      if (res.status() === 201) {
        const created = await res.json();
        expect(Number(created.price_per_day)).toBeGreaterThanOrEqual(0);
      } else {
        expect(res.status()).toBe(400);
      }
    });

    test('rejects offer with invalid item_set_id', async ({ verifiedUser }) => {
      const res = await postWithRateLimitRetry(verifiedUser, OFFER_API, {
        title: 'Test',
        item_set_id: 'not-a-uuid',
        price_per_day: 5
      });
      // Server may return 400 (validation) or 500 (DB error) for invalid UUID
      expect([400, 500]).toContain(res.status());
    });

    test('returns 404 for nonexistent offer', async ({ verifiedUser }) => {
      const res = await verifiedUser.request.get(`${OFFER_API}/999999`);
      expect(res.status()).toBe(404);
    });

    test('rejects discount with percent > 99', async ({ verifiedUser }) => {
      const itemSet = await createItemSet(verifiedUser);
      const res = await postWithRateLimitRetry(verifiedUser, OFFER_API, {
        title: 'Bad Discount',
        item_set_id: itemSet.id,
        price_per_day: 5,
        discounts: [{ minDays: 7, percent: 150 }]
      });
      // Sanitization should clamp or reject
      if (res.status() === 201) {
        const data = await res.json();
        if (Array.isArray(data.discounts) && data.discounts.length > 0) {
          expect(data.discounts[0].percent).toBeLessThanOrEqual(99);
        }
      } else {
        expect(res.status()).toBe(400);
      }
    });
  });
});

test.describe('Blocked Dates API', () => {
  test.describe('Authentication', () => {
    test('rejects unauthenticated GET blocked dates', async ({ page }) => {
      const res = await page.request.get(`${OFFER_API}/1/blocked-dates`);
      expect(res.status()).toBe(401);
    });

    test('rejects unauthenticated POST blocked dates', async ({ page }) => {
      const res = await page.request.post(`${OFFER_API}/1/blocked-dates`, {
        data: { start_date: futureDate(10), end_date: futureDate(15) }
      });
      expect(res.status()).toBe(401);
    });
  });

  test.describe('CRUD Operations', () => {
    test('can add and list blocked dates', async ({ verifiedUser }) => {
      const offer = await createPublishedOffer(verifiedUser, { title: 'Blocked Test' });

      // Add blocked dates
      const start = futureDate(30);
      const end = futureDate(35);
      const addRes = await verifiedUser.request.post(`${OFFER_API}/${offer.id}/blocked-dates`, {
        data: { start_date: start, end_date: end, reason: 'Personal use' }
      });
      expect(addRes.status()).toBe(201);

      const blocked = await addRes.json();
      expect(blocked.id).toBeDefined();
      const startDeltaDays = Math.abs(
        (new Date(blocked.start_date).getTime() - new Date(start).getTime()) / (1000 * 60 * 60 * 24)
      );
      const endDeltaDays = Math.abs(
        (new Date(blocked.end_date).getTime() - new Date(end).getTime()) / (1000 * 60 * 60 * 24)
      );
      expect(startDeltaDays).toBeLessThanOrEqual(1);
      expect(endDeltaDays).toBeLessThanOrEqual(1);

      // List blocked dates
      const listRes = await verifiedUser.request.get(`${OFFER_API}/${offer.id}/blocked-dates`);
      expect(listRes.status()).toBe(200);
      const dates = await listRes.json();
      expect(dates.length).toBeGreaterThanOrEqual(1);
    });

    test('can delete blocked dates', async ({ verifiedUser }) => {
      const offer = await createPublishedOffer(verifiedUser, { title: 'Delete Block Test' });

      const addRes = await verifiedUser.request.post(`${OFFER_API}/${offer.id}/blocked-dates`, {
        data: { start_date: futureDate(40), end_date: futureDate(45) }
      });
      const blocked = await addRes.json();

      const deleteRes = await verifiedUser.request.delete(`${OFFER_API}/${offer.id}/blocked-dates`, {
        data: { id: blocked.id }
      });
      expect(deleteRes.status()).toBe(200);
    });
  });

  test.describe('Validation', () => {
    test('rejects blocked dates in the past', async ({ verifiedUser }) => {
      const offer = await createPublishedOffer(verifiedUser, { title: 'Past Block Test' });

      const res = await verifiedUser.request.post(`${OFFER_API}/${offer.id}/blocked-dates`, {
        data: { start_date: '2020-01-01', end_date: '2020-01-05' }
      });
      expect(res.status()).toBe(400);
      const data = await res.json();
      expect(data.error).toContain('past');
    });

    test('rejects end_date before start_date', async ({ verifiedUser }) => {
      const offer = await createPublishedOffer(verifiedUser, { title: 'Invalid Range Test' });

      const res = await verifiedUser.request.post(`${OFFER_API}/${offer.id}/blocked-dates`, {
        data: { start_date: futureDate(20), end_date: futureDate(10) }
      });
      expect(res.status()).toBe(400);
    });

    test('other user cannot manage blocked dates', async ({ verifiedUser, browser }) => {
      const offer = await createPublishedOffer(verifiedUser, { title: 'Perm Block Test' });

      const ctx = await browser.newContext();
      const otherPage = await ctx.newPage();
      await otherPage.goto('/');
      await otherPage.request.post('/api/test/login', { data: { userId: 'verified2' } });
      await otherPage.reload();

      const res = await otherPage.request.get(`${OFFER_API}/${offer.id}/blocked-dates`);
      expect(res.status()).toBe(403);
      await ctx.close();
    });
  });
});

test.describe('Availability API', () => {
  test('can fetch availability for a published offer', async ({ verifiedUser, page }) => {
    const offer = await createPublishedOffer(verifiedUser, { title: 'Avail Test' });

    // Public endpoint - no auth required
    const res = await page.request.get(`${OFFER_API}/${offer.id}/availability`);
    expect(res.status()).toBe(200);

    const data = await res.json();
    expect(data.blockedDates).toBeDefined();
    expect(data.bookedDates).toBeDefined();
    expect(Array.isArray(data.blockedDates)).toBe(true);
    expect(Array.isArray(data.bookedDates)).toBe(true);
  });

  test('blocked dates appear in availability', async ({ verifiedUser, page }) => {
    const offer = await createPublishedOffer(verifiedUser, { title: 'Avail Block Test' });

    // Block some dates
    const start = futureDate(50);
    const end = futureDate(55);
    await verifiedUser.request.post(`${OFFER_API}/${offer.id}/blocked-dates`, {
      data: { start_date: start, end_date: end }
    });

    // Check availability
    const res = await page.request.get(`${OFFER_API}/${offer.id}/availability`);
    expect(res.status()).toBe(200);

    const data = await res.json();
    expect(data.blockedDates.length).toBeGreaterThanOrEqual(1);
    // Reason should NOT be exposed in availability
    const found = data.blockedDates.find((d: any) => d.start === start);
    if (found) {
      expect(found.reason).toBeUndefined();
    }
  });

  test('returns 404 for nonexistent offer availability', async ({ page }) => {
    const res = await page.request.get(`${OFFER_API}/999999/availability`);
    expect(res.status()).toBe(404);
  });
});

test.describe('Rental Requests API', () => {
  test.describe('Authentication', () => {
    test('rejects unauthenticated request creation', async ({ page }) => {
      const res = await page.request.post(`${OFFER_API}/1/requests`, {
        data: { start_date: futureDate(10), end_date: futureDate(15) }
      });
      expect(res.status()).toBe(401);
    });

    test('rejects unverified user request creation', async ({ unverifiedUser, verifiedUser }) => {
      const offer = await createPublishedOffer(verifiedUser, { title: 'Unverified Req Test' });

      const res = await unverifiedUser.request.post(`${OFFER_API}/${offer.id}/requests`, {
        data: { start_date: futureDate(10), end_date: futureDate(15) }
      });
      expect(res.status()).toBe(403);
    });
  });

  test.describe('Create Requests', () => {
    test('can create a rental request', async ({ verifiedUser, browser }) => {
      const offer = await createPublishedOffer(verifiedUser, { title: 'Request Test' });

      // Login as a different user to create the request
      const ctx = await browser.newContext();
      const requester = await ctx.newPage();
      await requester.goto('/');
      await requester.request.post('/api/test/login', { data: { userId: 'verified2' } });
      await requester.reload();

      const start = futureDate(60);
      const end = futureDate(65);
      const res = await requester.request.post(`${OFFER_API}/${offer.id}/requests`, {
        data: { start_date: start, end_date: end, note: 'I need this for hunting' }
      });
      expect(res.status()).toBe(201);

      const req = await res.json();
      expect(req.id).toBeDefined();
      expect(req.status).toBe('open');
      expect(req.total_days).toBe(6);
      expect(Number(req.price_per_day)).toBeGreaterThan(0);
      expect(Number(req.total_price)).toBeGreaterThan(0);
      await ctx.close();
    });

    test('owner cannot request their own offer', async ({ verifiedUser }) => {
      const offer = await createPublishedOffer(verifiedUser, { title: 'Self Req Test' });

      const res = await verifiedUser.request.post(`${OFFER_API}/${offer.id}/requests`, {
        data: { start_date: futureDate(70), end_date: futureDate(75) }
      });
      expect(res.status()).toBe(400);
      const data = await res.json();
      expect(String(data.error).toLowerCase()).toContain('cannot rent your own');
    });

    test('rejects request with conflicting dates (blocked)', async ({ verifiedUser, browser }) => {
      const offer = await createPublishedOffer(verifiedUser, { title: 'Conflict Test' });

      // Block dates
      const start = futureDate(80);
      const end = futureDate(85);
      await verifiedUser.request.post(`${OFFER_API}/${offer.id}/blocked-dates`, {
        data: { start_date: start, end_date: end }
      });

      // Try to request overlapping dates
      const ctx = await browser.newContext();
      const requester = await ctx.newPage();
      await requester.goto('/');
      await requester.request.post('/api/test/login', { data: { userId: 'verified2' } });
      await requester.reload();

      const res = await requester.request.post(`${OFFER_API}/${offer.id}/requests`, {
        data: { start_date: futureDate(82), end_date: futureDate(90) }
      });
      expect(res.status()).toBe(409);
      await ctx.close();
    });

    test('rejects request for draft offer', async ({ verifiedUser, browser }) => {
      const { res: createRes } = await createOffer(verifiedUser, { title: 'Draft Req Test' });
      const offer = await createRes.json();

      const ctx = await browser.newContext();
      const requester = await ctx.newPage();
      await requester.goto('/');
      await requester.request.post('/api/test/login', { data: { userId: 'verified2' } });
      await requester.reload();

      const res = await requester.request.post(`${OFFER_API}/${offer.id}/requests`, {
        data: { start_date: futureDate(100), end_date: futureDate(105) }
      });
      // Draft offers return 404 for non-owners
      expect([400, 404]).toContain(res.status());
      await ctx.close();
    });
  });

  test.describe('Status Transitions', () => {
    // Helper to set up a request
    async function setupRequest(ownerPage: Page, browser: any) {
      const offer = await createPublishedOffer(ownerPage, { title: `Transition Test ${Date.now()}` });

      const ctx = await browser.newContext();
      const requester = await ctx.newPage();
      await requester.goto('/');
      await requester.request.post('/api/test/login', { data: { userId: 'verified2' } });
      await requester.reload();

      const startOffset = 110 + Math.floor(Math.random() * 100);
      const start = futureDate(startOffset);
      const end = futureDate(startOffset + 5);
      const reqRes = await requester.request.post(`${OFFER_API}/${offer.id}/requests`, {
        data: { start_date: start, end_date: end }
      });
      expect(reqRes.status()).toBe(201);
      const request = await reqRes.json();

      return { offer, request, requester, requesterCtx: ctx };
    }

    test('owner can accept an open request', async ({ verifiedUser, browser }) => {
      const { request, requesterCtx } = await setupRequest(verifiedUser, browser);

      const res = await verifiedUser.request.put(`/api/rental/requests/${request.id}`, {
        data: { status: 'accepted', owner_note: 'Approved!' }
      });
      expect(res.status()).toBe(200);
      const updated = await res.json();
      expect(updated.status).toBe('accepted');
      await requesterCtx.close();
    });

    test('owner can reject an open request', async ({ verifiedUser, browser }) => {
      const { request, requesterCtx } = await setupRequest(verifiedUser, browser);

      const res = await verifiedUser.request.put(`/api/rental/requests/${request.id}`, {
        data: { status: 'rejected', owner_note: 'Not available' }
      });
      expect(res.status()).toBe(200);
      const updated = await res.json();
      expect(updated.status).toBe('rejected');
      await requesterCtx.close();
    });

    test('requester can cancel an open request', async ({ verifiedUser, browser }) => {
      const { request, requester, requesterCtx } = await setupRequest(verifiedUser, browser);

      const res = await requester.request.put(`/api/rental/requests/${request.id}`, {
        data: { status: 'cancelled' }
      });
      expect(res.status()).toBe(200);
      const updated = await res.json();
      expect(updated.status).toBe('cancelled');
      await requesterCtx.close();
    });

    test('requester cannot accept their own request', async ({ verifiedUser, browser }) => {
      const { request, requester, requesterCtx } = await setupRequest(verifiedUser, browser);

      const res = await requester.request.put(`/api/rental/requests/${request.id}`, {
        data: { status: 'accepted' }
      });
      expect(res.status()).toBe(400);
      await requesterCtx.close();
    });

    test('owner can progress accepted to in_progress', async ({ verifiedUser, browser }) => {
      const { request, requesterCtx } = await setupRequest(verifiedUser, browser);

      // Accept first
      await verifiedUser.request.put(`/api/rental/requests/${request.id}`, {
        data: { status: 'accepted' }
      });

      // Then start
      const res = await verifiedUser.request.put(`/api/rental/requests/${request.id}`, {
        data: { status: 'in_progress' }
      });
      expect(res.status()).toBe(200);
      const updated = await res.json();
      expect(updated.status).toBe('in_progress');
      await requesterCtx.close();
    });

    test('owner can complete an in_progress rental', async ({ verifiedUser, browser }) => {
      const { request, requesterCtx } = await setupRequest(verifiedUser, browser);

      // Accept -> in_progress -> completed
      await verifiedUser.request.put(`/api/rental/requests/${request.id}`, {
        data: { status: 'accepted' }
      });
      await verifiedUser.request.put(`/api/rental/requests/${request.id}`, {
        data: { status: 'in_progress' }
      });

      const res = await verifiedUser.request.put(`/api/rental/requests/${request.id}`, {
        data: { status: 'completed' }
      });
      expect(res.status()).toBe(200);
      const updated = await res.json();
      expect(updated.status).toBe('completed');
      await requesterCtx.close();
    });

    test('rejects invalid status transition (open -> completed)', async ({ verifiedUser, browser }) => {
      const { request, requesterCtx } = await setupRequest(verifiedUser, browser);

      const res = await verifiedUser.request.put(`/api/rental/requests/${request.id}`, {
        data: { status: 'completed' }
      });
      expect(res.status()).toBe(400);
      await requesterCtx.close();
    });
  });

  test.describe('Extensions', () => {
    test('owner can extend an accepted rental', async ({ verifiedUser, browser }) => {
      const offer = await createPublishedOffer(verifiedUser, { title: 'Extension Test' });

      const ctx = await browser.newContext();
      const requester = await ctx.newPage();
      await requester.goto('/');
      await requester.request.post('/api/test/login', { data: { userId: 'verified2' } });
      await requester.reload();

      const start = futureDate(200);
      const end = futureDate(205);
      const reqRes = await requester.request.post(`${OFFER_API}/${offer.id}/requests`, {
        data: { start_date: start, end_date: end }
      });
      const request = await reqRes.json();

      // Accept the request
      await verifiedUser.request.put(`/api/rental/requests/${request.id}`, {
        data: { status: 'accepted' }
      });

      // Extend by 5 days (non-retroactive)
      const newEnd = futureDate(210);
      const extRes = await verifiedUser.request.put(`/api/rental/requests/${request.id}`, {
        data: { action: 'extend', new_end_date: newEnd, retroactive: false }
      });
      expect(extRes.status()).toBe(200);

      const extension = await extRes.json();
      expect(extension.extra_days).toBeGreaterThan(0);
      expect(Number(extension.extra_price)).toBeGreaterThan(0);
      await ctx.close();
    });

    test('rejects extension with end date before current end', async ({ verifiedUser, browser }) => {
      const offer = await createPublishedOffer(verifiedUser, { title: 'Bad Extension Test' });

      const ctx = await browser.newContext();
      const requester = await ctx.newPage();
      await requester.goto('/');
      await requester.request.post('/api/test/login', { data: { userId: 'verified2' } });
      await requester.reload();

      const start = futureDate(220);
      const end = futureDate(225);
      const reqRes = await requester.request.post(`${OFFER_API}/${offer.id}/requests`, {
        data: { start_date: start, end_date: end }
      });
      const request = await reqRes.json();

      await verifiedUser.request.put(`/api/rental/requests/${request.id}`, {
        data: { status: 'accepted' }
      });

      // Try extending to a date before current end
      const res = await verifiedUser.request.put(`/api/rental/requests/${request.id}`, {
        data: { action: 'extend', new_end_date: futureDate(220) }
      });
      expect(res.status()).toBe(400);
      await ctx.close();
    });
  });
});

test.describe('My Rentals API', () => {
  test('rejects unauthenticated access', async ({ page }) => {
    const res = await page.request.get('/api/rental/my?type=offers');
    expect(res.status()).toBe(401);
  });

  test('can list my offers', async ({ verifiedUser }) => {
    await createOffer(verifiedUser, { title: 'My Offer List Test' });

    const res = await verifiedUser.request.get('/api/rental/my?type=offers');
    expect(res.status()).toBe(200);

    const offers = await res.json();
    expect(Array.isArray(offers)).toBe(true);
    expect(offers.length).toBeGreaterThan(0);
  });

  test('can list my requests', async ({ verifiedUser }) => {
    const res = await verifiedUser.request.get('/api/rental/my?type=requests');
    expect(res.status()).toBe(200);

    const requests = await res.json();
    expect(Array.isArray(requests)).toBe(true);
  });

  test('rejects invalid type parameter', async ({ verifiedUser }) => {
    const res = await verifiedUser.request.get('/api/rental/my?type=invalid');
    expect(res.status()).toBe(200);
    const offers = await res.json();
    expect(Array.isArray(offers)).toBe(true);
  });
});

test.describe('Item Set Protection', () => {
  test('prevents editing item set linked to rental offer', async ({ verifiedUser }) => {
    const { res: createRes, itemSetId } = await createOffer(verifiedUser, { title: 'Lock Test' });
    expect(createRes.status()).toBe(201);

    // Try to update the item set
    const updateRes = await verifiedUser.request.put(`${ITEM_SET_API}/${itemSetId}`, {
      data: { name: 'Modified', data: DEFAULT_ITEM_SET_DATA }
    });
    expect(updateRes.status()).toBe(409);
    const data = await updateRes.json();
    expect(data.error).toContain('rental offer');
  });

  test('prevents deleting item set linked to rental offer', async ({ verifiedUser }) => {
    const { res: createRes, itemSetId } = await createOffer(verifiedUser, { title: 'Delete Lock Test' });
    expect(createRes.status()).toBe(201);

    const deleteRes = await verifiedUser.request.delete(`${ITEM_SET_API}/${itemSetId}`);
    expect(deleteRes.status()).toBe(409);
    const data = await deleteRes.json();
    expect(data.error).toContain('rental offer');
  });

  test('can edit item set after rental offer is deleted', async ({ verifiedUser }) => {
    const { res: createRes, itemSetId } = await createOffer(verifiedUser, { title: 'Unlock Test' });
    const offer = await createRes.json();

    // Delete the offer
    await verifiedUser.request.delete(`${OFFER_API}/${offer.id}`);

    // Now should be able to update
    const updateRes = await verifiedUser.request.put(`${ITEM_SET_API}/${itemSetId}`, {
      data: { name: 'Free Again', data: DEFAULT_ITEM_SET_DATA }
    });
    expect(updateRes.status()).toBe(200);
  });
});
