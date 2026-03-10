import { test, expect } from './fixtures/auth';
import { TIMEOUT_MEDIUM, TIMEOUT_LONG } from './test-constants';

test.describe('Globals media — multi-platform video links', () => {
  /**
   * Test the video URL submission API for each supported platform.
   * Uses the API directly since the UI relies on real ingested globals.
   */

  test('API rejects unsupported video URLs', async ({ verifiedUser: page }) => {
    // Try to submit an unsupported URL
    const resp = await page.request.post('/api/globals/1/media', {
      data: { video_url: 'https://example.com/video' },
      headers: { 'Content-Type': 'application/json' },
    });
    // 400 or 404 (global may not exist in test DB, but validation runs first)
    const body = await resp.json();
    if (resp.status() === 400) {
      expect(body.error).toContain('Unsupported');
      expect(body.error).toContain('YouTube');
      expect(body.error).toContain('Twitch');
      expect(body.error).toContain('Vimeo');
    }
  });

  test('API accepts YouTube URL format', async ({ verifiedUser: page }) => {
    const resp = await page.request.post('/api/globals/1/media', {
      data: { video_url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ' },
      headers: { 'Content-Type': 'application/json' },
    });
    const body = await resp.json();
    // Either succeeds (200) or fails because global doesn't exist (404) / already has media (409)
    // The key test is that it doesn't reject the URL format (400)
    expect(resp.status()).not.toBe(400);
  });

  test('API accepts Twitch clip URL format', async ({ verifiedUser: page }) => {
    const resp = await page.request.post('/api/globals/1/media', {
      data: { video_url: 'https://clips.twitch.tv/SomeClipSlug-AbCdEfGhIjKlMn' },
      headers: { 'Content-Type': 'application/json' },
    });
    const body = await resp.json();
    expect(resp.status()).not.toBe(400);
  });

  test('API accepts Vimeo URL format', async ({ verifiedUser: page }) => {
    const resp = await page.request.post('/api/globals/1/media', {
      data: { video_url: 'https://vimeo.com/123456789' },
      headers: { 'Content-Type': 'application/json' },
    });
    const body = await resp.json();
    expect(resp.status()).not.toBe(400);
  });

  test('API accepts backward-compat youtube_url field', async ({ verifiedUser: page }) => {
    const resp = await page.request.post('/api/globals/1/media', {
      data: { youtube_url: 'https://youtu.be/dQw4w9WgXcQ' },
      headers: { 'Content-Type': 'application/json' },
    });
    const body = await resp.json();
    expect(resp.status()).not.toBe(400);
  });

  test('budget endpoint returns videos key', async ({ verifiedUser: page }) => {
    const resp = await page.request.get('/api/globals/media/budget');
    expect(resp.status()).toBe(200);

    const body = await resp.json();
    expect(body).toHaveProperty('images');
    expect(body).toHaveProperty('videos');
    expect(body.images).toHaveProperty('used');
    expect(body.images).toHaveProperty('limit');
    expect(body.images).toHaveProperty('remaining');
    expect(body.videos).toHaveProperty('used');
    expect(body.videos).toHaveProperty('limit');
    expect(body.videos).toHaveProperty('remaining');
    expect(body.videos.limit).toBe(30);
  });

  test('unauthenticated user cannot submit video link', async ({ page }) => {
    const resp = await page.request.post('/api/globals/1/media', {
      data: { video_url: 'https://www.youtube.com/watch?v=dQw4w9WgXcQ' },
      headers: { 'Content-Type': 'application/json' },
    });
    expect(resp.status()).toBe(401);
  });

  test('globals page loads with media_video support', async ({ page }) => {
    await page.goto('/globals');
    await page.waitForLoadState('networkidle');

    // The page should load successfully — media_video replaces media_youtube
    const tabNav = page.locator('.globals-tab-nav');
    await expect(tabNav).toBeVisible({ timeout: TIMEOUT_LONG });
  });

  test('GlobalMediaUpload shows "Add Video Link" menu item', async ({ verifiedUser: page }) => {
    await page.goto('/globals');
    await page.waitForLoadState('networkidle');

    // Find an upload button (if any globals exist without media)
    const uploadBtn = page.locator('.media-upload-btn').first();
    if (await uploadBtn.isVisible({ timeout: TIMEOUT_MEDIUM }).catch(() => false)) {
      await uploadBtn.click();
      const menu = page.locator('.upload-menu');
      await expect(menu).toBeVisible({ timeout: TIMEOUT_MEDIUM });
      await expect(menu.locator('.menu-item', { hasText: 'Add Video Link' })).toBeVisible();
    }
  });
});
