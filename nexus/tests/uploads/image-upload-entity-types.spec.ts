import { test, expect } from '../fixtures/auth';

/**
 * Image Upload Entity Type Tests
 *
 * Verifies:
 * 1. Sub-type entity types (misctool, absorber, etc.) are accepted by the upload API
 * 2. Existing parent entity types still work
 * 3. Invalid entity types are rejected
 */

const UPLOAD_API = '/api/uploads/entity-image';

// 32x32 red pixel PNG (meets MIN_IMAGE_DIMENSION=32 requirement)
const TEST_PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAIAAAD8GO2jAAAACXBIWXMAAAPoAAAD6AG1e1JrAAAANklEQVR4nO3WuQkAQAwDwem/aV0VhgsWnAuMnjVOTwJ6kVy0gqaqWG2qwVmTKaoQeAkdfU3XDzLD/C4XqhOlAAAAAElFTkSuQmCC',
  'base64'
);

/**
 * Helper to POST a test image upload
 */
async function uploadImage(page: any, entityType: string, entityId = '999999') {
  const formData = new URLSearchParams();
  // We need multipart form data, so use the request API directly
  return page.request.post(UPLOAD_API, {
    multipart: {
      image: {
        name: 'test.png',
        mimeType: 'image/png',
        buffer: TEST_PNG,
      },
      entityType,
      entityId,
    },
  });
}

test.describe('Image upload entity type validation', () => {

  test('accepts tool sub-types', async ({ verifiedUser }) => {
    const subTypes = ['misctool', 'refiner', 'scanner', 'finder', 'excavator', 'teleportationchip', 'effectchip'];

    for (const subType of subTypes) {
      const response = await uploadImage(verifiedUser, subType);
      expect(response.status(), `${subType} should be accepted`).not.toBe(400);
    }
  });

  test('accepts attachment sub-types', async ({ verifiedUser }) => {
    const subTypes = ['weaponamplifier', 'weaponvisionattachment', 'absorber', 'finderamplifier', 'armorplating', 'enhancer', 'mindforceimplant'];

    for (const subType of subTypes) {
      const response = await uploadImage(verifiedUser, subType);
      expect(response.status(), `${subType} should be accepted`).not.toBe(400);
    }
  });

  test('accepts furnishing sub-types', async ({ verifiedUser }) => {
    const subTypes = ['furniture', 'decoration', 'storagecontainer', 'sign'];

    for (const subType of subTypes) {
      const response = await uploadImage(verifiedUser, subType);
      expect(response.status(), `${subType} should be accepted`).not.toBe(400);
    }
  });

  test('accepts other sub-types (capsule, medicalchip, shop)', async ({ verifiedUser }) => {
    const subTypes = ['capsule', 'medicalchip', 'shop'];

    for (const subType of subTypes) {
      const response = await uploadImage(verifiedUser, subType);
      expect(response.status(), `${subType} should be accepted`).not.toBe(400);
    }
  });

  test('still accepts existing parent entity types', async ({ verifiedUser }) => {
    const parentTypes = ['weapon', 'tool', 'attachment', 'clothing', 'material'];

    for (const parentType of parentTypes) {
      const response = await uploadImage(verifiedUser, parentType);
      expect(response.status(), `${parentType} should still be accepted`).not.toBe(400);
    }
  });

  test('rejects invalid entity type', async ({ verifiedUser }) => {
    const response = await uploadImage(verifiedUser, 'notarealtype');
    expect(response.status()).toBe(400);

    const body = await response.json();
    expect(body.message || body.error).toContain('Invalid entity type');
  });

  test('requires authentication', async ({ page }) => {
    const response = await uploadImage(page, 'weapon');
    expect(response.status()).toBe(401);
  });
});
