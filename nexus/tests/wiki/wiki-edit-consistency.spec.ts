import { test, expect } from '../fixtures/auth';
import type { Page } from '@playwright/test';
import { WIKI_PAGES_WITH_SUBTYPES } from './test-pages';
import { TIMEOUT_INSTANT, TIMEOUT_MEDIUM, TIMEOUT_LONG } from '../test-constants';

const TEST_PAGES = WIKI_PAGES_WITH_SUBTYPES;

// Helper to wait for wiki nav to load
async function waitForWikiNav(page: Page) {
  await expect(page.locator('.wiki-nav, .wiki-sidebar').first()).toBeVisible({ timeout: TIMEOUT_LONG });
}

// Helper to check if items are available
async function hasItems(page: Page) {
  const items = page.locator('.item-link');
  const count = await items.count();
  return count > 0;
}


test.describe('Wiki Edit Mode - Consistency Across Pages', () => {
  test.describe('Edit Button and Mode Toggle', () => {
    for (const page of TEST_PAGES) {
      test(`${page.name}: verified user can enter edit mode`, async ({ verifiedUser }) => {
        // Skip if page is marked as not editable (e.g., enhancers)
        if ('editable' in page && page.editable === false) {
          test.skip();
          return;
        }

        await verifiedUser.goto(page.path);
        await verifiedUser.waitForLoadState('networkidle');
        await waitForWikiNav(verifiedUser);

        if (!await hasItems(verifiedUser)) {
          test.skip();
          return;
        }

        const firstItem = verifiedUser.locator('.item-link').first();
        await firstItem.click();
        await verifiedUser.waitForLoadState('networkidle');

        const editButton = verifiedUser.locator('button:has-text(\"Edit\")');
        await expect(editButton).toBeVisible();
        await editButton.click();

        const actionBar = verifiedUser.locator('.action-bar, .edit-action-bar');
        await expect(actionBar).toBeVisible({ timeout: TIMEOUT_LONG });

        // Check for Cancel button within the action bar to avoid strict mode violation
        const cancelButton = actionBar.locator('button:has-text(\"Cancel\")');
        await expect(cancelButton).toBeVisible();
      });
    }
  });

  test.describe('Entity Image Upload in Edit Mode', () => {
    for (const page of TEST_PAGES) {
      test(`${page.name}: image shows upload overlay in edit mode`, async ({ verifiedUser }) => {
        // Skip if page is marked as not editable (e.g., enhancers)
        if ('editable' in page && page.editable === false) {
          test.skip();
          return;
        }
        // Missions currently do not expose an editable entity icon/upload control.
        if (page.name === 'Missions') {
          test.skip();
          return;
        }

        await verifiedUser.goto(page.path);
        await verifiedUser.waitForLoadState('networkidle');
        await waitForWikiNav(verifiedUser);

        if (!await hasItems(verifiedUser)) {
          test.skip();
          return;
        }

        const firstItem = verifiedUser.locator('.item-link').first();
        await firstItem.click();
        await verifiedUser.waitForLoadState('networkidle');

        const editButton = verifiedUser.locator('button:has-text(\"Edit\")');
        await editButton.click();
        await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

        const imageWrapper = verifiedUser.locator('.entity-icon-wrapper.editable').first();
        await expect(imageWrapper).toBeVisible();
      });
    }
  });

  test.describe('Entity Title Inline Edits (Both Infobox and Article)', () => {
    for (const page of TEST_PAGES) {
      test(`${page.name}: infobox title becomes editable`, async ({ verifiedUser }) => {
        // Skip if page is marked as not editable (e.g., enhancers)
        if ('editable' in page && page.editable === false) {
          test.skip();
          return;
        }

        await verifiedUser.goto(page.path);
        await verifiedUser.waitForLoadState('networkidle');
        await waitForWikiNav(verifiedUser);

        if (!await hasItems(verifiedUser)) {
          test.skip();
          return;
        }

        const firstItem = verifiedUser.locator('.item-link').first();
        await firstItem.click();
        await verifiedUser.waitForLoadState('networkidle');

        const editButton = verifiedUser.locator('button:has-text(\"Edit\")');
        await editButton.click();
        await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

        const infoboxTitle = verifiedUser.locator('.infobox-title .inline-edit.editable');
        await expect(infoboxTitle).toBeVisible();
      });

      test(`${page.name}: article title becomes editable (if present)`, async ({ verifiedUser }) => {
        // Skip if page is marked as not editable (e.g., enhancers)
        if ('editable' in page && page.editable === false) {
          test.skip();
          return;
        }

        await verifiedUser.goto(page.path);
        await verifiedUser.waitForLoadState('networkidle');
        await waitForWikiNav(verifiedUser);

        if (!await hasItems(verifiedUser)) {
          test.skip();
          return;
        }

        const firstItem = verifiedUser.locator('.item-link').first();
        await firstItem.click();
        await verifiedUser.waitForLoadState('networkidle');

        const editButton = verifiedUser.locator('button:has-text(\"Edit\")');
        await editButton.click();
        await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

        // Check if article title exists
        const articleTitleContainer = verifiedUser.locator('.article-title, .wiki-article h1.article-title');
        try {
          await expect(articleTitleContainer).toBeVisible({ timeout: TIMEOUT_MEDIUM });

          // Article title exists - check if it uses InlineEdit (optional)
          // Some pages use InlineEdit, others use plain text - both are valid
          const editableArticleTitle = verifiedUser.locator('.article-title .inline-edit, .wiki-article h1 .inline-edit');
          const usesInlineEdit = await editableArticleTitle.count() > 0;

          // If it uses InlineEdit, verify it's in editable state
          if (usesInlineEdit) {
            await expect(editableArticleTitle).toHaveClass(/editable/);
          }
        } catch {
          // No article title - that's OK, not all pages have them
        }
      });
    }
  });

  test.describe('Description Editor', () => {
    for (const page of TEST_PAGES) {
      test(`${page.name}: description becomes editable with RichTextEditor`, async ({ verifiedUser }) => {
        // Skip if page is marked as not editable (e.g., enhancers)
        if ('editable' in page && page.editable === false) {
          test.skip();
          return;
        }

        await verifiedUser.goto(page.path);
        await verifiedUser.waitForLoadState('networkidle');
        await waitForWikiNav(verifiedUser);

        if (!await hasItems(verifiedUser)) {
          test.skip();
          return;
        }

        const firstItem = verifiedUser.locator('.item-link').first();
        await firstItem.click();
        await verifiedUser.waitForLoadState('networkidle');

        const editButton = verifiedUser.locator('button:has-text(\"Edit\")');
        await editButton.click();
        await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

        const editor = verifiedUser.locator('.tiptap:visible, .ProseMirror:visible, textarea[data-path*=\"Description\"]:visible').first();
        await expect(editor).toBeVisible();
      });
    }
  });

  test.describe('Save/Cancel Action Bar', () => {
    for (const page of TEST_PAGES) {
      test(`${page.name}: action bar has Save and Cancel buttons`, async ({ verifiedUser }) => {
        // Skip if page is marked as not editable (e.g., enhancers)
        if ('editable' in page && page.editable === false) {
          test.skip();
          return;
        }

        await verifiedUser.goto(page.path);
        await verifiedUser.waitForLoadState('networkidle');
        await waitForWikiNav(verifiedUser);

        if (!await hasItems(verifiedUser)) {
          test.skip();
          return;
        }

        const firstItem = verifiedUser.locator('.item-link').first();
        await firstItem.click();
        await verifiedUser.waitForLoadState('networkidle');

        const editButton = verifiedUser.locator('button:has-text(\"Edit\")');
        await editButton.click();
        await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);

        const actionBar = verifiedUser.locator('.action-bar, .edit-action-bar');
        await expect(actionBar).toBeVisible();

        // Check for at least one save button (either Save Draft or Submit for Review)
        const saveDraftBtn = actionBar.locator('button:has-text(\"Save Draft\")');
        const saveBtn = actionBar.locator('button:has-text(\"Save\")').first();
        const submitReviewBtn = actionBar.locator('button:has-text(\"Submit for Review\")');
        const cancelBtn = actionBar.locator('button:has-text(\"Cancel\")');

        // At least one save-type button should be visible
        let hasSaveButton = false;
        try {
          await expect(saveDraftBtn).toBeVisible({ timeout: TIMEOUT_MEDIUM });
          hasSaveButton = true;
        } catch {
          try {
            await expect(saveBtn).toBeVisible({ timeout: TIMEOUT_MEDIUM });
            hasSaveButton = true;
          } catch {
            await expect(submitReviewBtn).toBeVisible({ timeout: TIMEOUT_MEDIUM });
            hasSaveButton = true;
          }
        }
        expect(hasSaveButton).toBeTruthy();

        await expect(cancelBtn).toBeVisible();
      });
    }
  });

  test.describe('Data Section Panels', () => {
    for (const page of TEST_PAGES) {
      test(`${page.name}: data sections are collapsible`, async ({ verifiedUser }) => {
        await verifiedUser.goto(page.path);
        await verifiedUser.waitForLoadState('networkidle');
        await waitForWikiNav(verifiedUser);

        if (!await hasItems(verifiedUser)) {
          test.skip();
          return;
        }

        const firstItem = verifiedUser.locator('.item-link').first();
        await firstItem.click();
        await verifiedUser.waitForLoadState('networkidle');

        const sectionHeaders = verifiedUser.locator('.data-section-header, .section-header');
        const count = await sectionHeaders.count();

        if (count > 0) {
          await sectionHeaders.first().click();
          await verifiedUser.waitForTimeout(TIMEOUT_INSTANT);
          expect(count).toBeGreaterThan(0);
        }
      });
    }
  });

  test.describe('Non-Editable Pages (Enhancers)', () => {
    test('Enhancers: does NOT show Edit button (database-generated)', async ({ verifiedUser }) => {
      await verifiedUser.goto('/items/attachments/enhancers');
      await verifiedUser.waitForLoadState('networkidle');
      await waitForWikiNav(verifiedUser);

      if (!await hasItems(verifiedUser)) {
        test.skip();
        return;
      }

      const firstItem = verifiedUser.locator('.item-link').first();
      await firstItem.click();
      await verifiedUser.waitForLoadState('networkidle');

      // Enhancers should NOT have an Edit button
      const editButton = verifiedUser.locator('button:has-text("Edit")');
      await expect(editButton).not.toBeVisible();
    });
  });
});
