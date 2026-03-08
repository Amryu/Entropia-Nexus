import { test, expect } from '../fixtures/auth';

/**
 * Image Upload Security Tests
 *
 * Verifies:
 * 1. Path traversal prevention in preview endpoint
 * 2. Authorization checks on link-image endpoint
 * 3. Rate limiting / size checks on profile image upload
 * 4. Entity type/ID validation on approved images endpoint
 * 5. Error messages don't leak internal details
 */

const PREVIEW_API = '/api/uploads/preview';
const LINK_IMAGE_API = '/api/uploads/link-image';
const APPROVED_API = '/api/uploads/approved';
const PROFILE_IMAGE_API = '/api/image/user';

// 32x32 red pixel PNG
const TEST_PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAIAAAD8GO2jAAAACXBIWXMAAAPoAAAD6AG1e1JrAAAANklEQVR4nO3WuQkAQAwDwem/aV0VhgsWnAuMnjVOTwJ6kVy0gqaqWG2qwVmTKaoQeAkdfU3XDzLD/C4XqhOlAAAAAElFTkSuQmCC',
  'base64'
);

test.describe('Preview endpoint path traversal prevention', () => {
  test('rejects path traversal with dot-dot', async ({ page }) => {
    const response = await page.request.get(`${PREVIEW_API}/..`);
    expect(response.status()).toBe(400);
  });

  test('rejects path traversal with encoded backslash', async ({ page }) => {
    const response = await page.request.get(`${PREVIEW_API}/..%5C..%5Capproved%5Cweapon%5Ctest`);
    expect(response.status()).toBe(400);
  });

  test('rejects non-UUID tempId', async ({ page }) => {
    const response = await page.request.get(`${PREVIEW_API}/not-a-uuid`);
    expect(response.status()).toBe(400);
  });

  test('rejects empty tempId with just spaces', async ({ page }) => {
    const response = await page.request.get(`${PREVIEW_API}/%20%20%20`);
    expect(response.status()).toBe(400);
  });

  test('accepts valid UUID format (returns 404 for non-existent)', async ({ page }) => {
    const response = await page.request.get(`${PREVIEW_API}/12345678-1234-1234-1234-123456789abc`);
    expect(response.status()).toBe(404);
  });
});

test.describe('Link-image endpoint authorization', () => {
  test('rejects unauthenticated requests', async ({ page }) => {
    const response = await page.request.post(LINK_IMAGE_API, {
      data: { entityType: 'weapon', entityId: '1', sourceEntityId: '2' },
    });
    expect(response.status()).toBe(401);
  });

  test('rejects verified user without wiki.approve grant', async ({ verifiedUser }) => {
    const response = await verifiedUser.request.post(LINK_IMAGE_API, {
      data: { entityType: 'weapon', entityId: '1', sourceEntityId: '2' },
    });
    expect(response.status()).toBe(403);
  });

  test('allows admin user', async ({ adminUser }) => {
    // Admin has admin.panel grant; request may fail for other reasons (no source image)
    // but should NOT be 403
    const response = await adminUser.request.post(LINK_IMAGE_API, {
      data: { entityType: 'weapon', entityId: '1', sourceEntityId: '2' },
    });
    expect(response.status()).not.toBe(403);
  });
});

test.describe('Profile image upload rate limiting', () => {
  test('rejects oversized Content-Length', async ({ verifiedUser }) => {
    const response = await verifiedUser.request.post(`${PROFILE_IMAGE_API}/verified1`, {
      multipart: {
        image: {
          name: 'test.png',
          mimeType: 'image/png',
          buffer: TEST_PNG,
        },
      },
      headers: {
        'Content-Length': '999999999',
      },
    });
    expect(response.status()).toBe(413);
  });
});

test.describe('Approved images endpoint validation', () => {
  test('rejects invalid entity type', async ({ page }) => {
    const response = await page.request.get(`${APPROVED_API}/notarealtype/12345`);
    expect(response.status()).toBe(400);
  });

  test('rejects path traversal in entity type', async ({ page }) => {
    const response = await page.request.get(`${APPROVED_API}/..%5C..%5Cetc/passwd`);
    expect(response.status()).toBe(400);
  });

  test('rejects path traversal in entity ID', async ({ page }) => {
    const response = await page.request.get(`${APPROVED_API}/weapon/..%5C..%5C..%5Cetc`);
    expect(response.status()).toBe(400);
  });

  test('rejects oversized entity ID', async ({ page }) => {
    const longId = 'a'.repeat(201);
    const response = await page.request.get(`${APPROVED_API}/weapon/${longId}`);
    expect(response.status()).toBe(400);
  });
});

test.describe('Error message leakage prevention', () => {
  test('entity-image 500 errors use generic message', async ({ verifiedUser }) => {
    // Upload with a file that will fail processing (0 bytes after form parse trick)
    const response = await verifiedUser.request.post('/api/uploads/entity-image', {
      multipart: {
        image: {
          name: 'test.png',
          mimeType: 'image/png',
          buffer: Buffer.from('not a real image'),
        },
        entityType: 'weapon',
        entityId: '999999',
      },
    });

    if (response.status() >= 400) {
      const body = await response.text();
      expect(body).not.toContain('uploads/');
      expect(body).not.toContain('\\');
      expect(body).not.toContain('C:');
    }
  });
});
