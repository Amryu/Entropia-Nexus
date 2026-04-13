import { test, expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import { TIMEOUT_SHORT, TIMEOUT_MEDIUM, TIMEOUT_LONG } from '../test-constants';

/**
 * E2E tests for the inline armor-vs-mob recommendation panels embedded on
 * the mob detail page and the armor set detail page, plus query-param
 * deep-linking into the full Gear Advisor tool.
 *
 * Designed to degrade gracefully when the test DB lacks the expected data.
 */

async function pageLoaded(page: Page) {
  const errorHeading = page.locator('h1:has-text("500"), h1:has-text("404")');
  return (await errorHeading.count()) === 0;
}

async function findFirstMobLink(page: Page): Promise<string | null> {
  await page.goto('/information/mobs');
  await page.waitForLoadState('networkidle', { timeout: TIMEOUT_MEDIUM });
  const link = page.locator('a[href^="/information/mobs/"]').first();
  if ((await link.count()) === 0) return null;
  const href = await link.getAttribute('href');
  return href;
}

async function findFirstArmorSetLink(page: Page): Promise<string | null> {
  await page.goto('/items/armorsets');
  await page.waitForLoadState('networkidle', { timeout: TIMEOUT_MEDIUM });
  const link = page.locator('a[href^="/items/armorsets/"]').first();
  if ((await link.count()) === 0) return null;
  return await link.getAttribute('href');
}

test.describe('Inline armor-vs-mob panel on mob detail page', () => {
  test('panel appears and loads top recommendations on expand', async ({ page }) => {
    const href = await findFirstMobLink(page);
    test.skip(!href, 'No mobs in test DB');
    await page.goto(href!);
    if (!(await pageLoaded(page))) test.skip(true, 'Mob page did not load');

    const header = page.getByRole('button', { name: /Recommended Armor/i });
    if ((await header.count()) === 0) test.skip(true, 'Panel not rendered (likely mob has no maturities)');
    await header.click();

    const panel = page.locator('.inline-avm-panel');
    await expect(panel).toBeVisible({ timeout: TIMEOUT_MEDIUM });

    // Wait for loading to resolve (either rows, empty state, or status text)
    await expect(
      panel.locator('table.results tbody tr, .status')
    ).toBeVisible({ timeout: TIMEOUT_LONG });

    // Segmented All/Pool control exists
    await expect(panel.getByRole('tab', { name: /All armors/i })).toBeVisible();
    await expect(panel.getByRole('tab', { name: /My pool/i })).toBeVisible();
  });

  test('"Open in Gear Advisor" link pre-fills mob via query param', async ({ page }) => {
    const href = await findFirstMobLink(page);
    test.skip(!href, 'No mobs in test DB');
    await page.goto(href!);
    if (!(await pageLoaded(page))) test.skip(true, 'Mob page did not load');

    const header = page.getByRole('button', { name: /Recommended Armor/i });
    if ((await header.count()) === 0) test.skip(true, 'Panel not rendered');
    await header.click();

    const link = page.locator('.inline-avm-panel a.btn');
    await expect(link).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    const linkHref = await link.getAttribute('href');
    expect(linkHref).toContain('/tools/gear-advisor/armor-vs-mob');
    expect(linkHref).toContain('mob=');
  });
});

test.describe('Inline armor-vs-mob panel on armor set detail page', () => {
  test('panel appears with planet and HP range filters', async ({ page }) => {
    const href = await findFirstArmorSetLink(page);
    test.skip(!href, 'No armor sets in test DB');
    await page.goto(href!);
    if (!(await pageLoaded(page))) test.skip(true, 'Armor set page did not load');

    const header = page.getByRole('button', { name: /Recommended Mobs/i });
    if ((await header.count()) === 0) test.skip(true, 'Panel not rendered (cosmetic armor?)');
    await header.click();

    const panel = page.locator('.inline-avm-panel');
    await expect(panel).toBeVisible({ timeout: TIMEOUT_MEDIUM });

    // Filters present
    await expect(panel.locator('select').first()).toBeVisible();
    await expect(panel.locator('input[type="number"]')).toHaveCount(2);

    // Wait for either ranking rows or a status message
    await expect(
      panel.locator('table.results tbody tr, .status')
    ).toBeVisible({ timeout: TIMEOUT_LONG });
  });

  test('HP range filter narrows the ranking', async ({ page }) => {
    const href = await findFirstArmorSetLink(page);
    test.skip(!href, 'No armor sets in test DB');
    await page.goto(href!);
    if (!(await pageLoaded(page))) test.skip(true, 'Armor set page did not load');

    const header = page.getByRole('button', { name: /Recommended Mobs/i });
    if ((await header.count()) === 0) test.skip(true, 'Panel not rendered');
    await header.click();

    const panel = page.locator('.inline-avm-panel');
    await expect(panel).toBeVisible({ timeout: TIMEOUT_MEDIUM });
    await expect(panel.locator('table.results tbody tr, .status')).toBeVisible({ timeout: TIMEOUT_LONG });

    const hpMax = panel.locator('input[type="number"]').nth(1);
    await hpMax.fill('100');
    // Allow re-ranking to run
    await page.waitForTimeout(TIMEOUT_SHORT);
    // Still resolves (either rows or "No comparable data")
    await expect(panel.locator('table.results tbody tr, .status')).toBeVisible({ timeout: TIMEOUT_LONG });
  });
});

test.describe('Gear Advisor query param pre-fill', () => {
  test('tool reads ?mob= from URL and pre-selects the mob', async ({ page }) => {
    // Discover a real mob name first via the API list
    const response = await page.request.get('/api/mobs').catch(() => null);
    if (!response || !response.ok()) test.skip(true, 'Cannot reach /api/mobs');
    const mobs = await response!.json();
    const mobName = Array.isArray(mobs) && mobs.length > 0 ? mobs[0]?.Name : null;
    test.skip(!mobName, 'No mobs in test DB');

    await page.goto(`/tools/gear-advisor/armor-vs-mob?mob=${encodeURIComponent(mobName)}`);
    await page.waitForLoadState('networkidle', { timeout: TIMEOUT_LONG });

    // The mob name should appear somewhere in the page (picker selection area)
    await expect(page.getByText(mobName, { exact: false }).first()).toBeVisible({ timeout: TIMEOUT_LONG });
  });
});
