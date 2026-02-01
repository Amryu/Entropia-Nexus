# wiki-edit-consistency.spec.ts - Anti-pattern Removal

## Date: 2026-02-01

## Summary
Removed all `.catch(() => false)` and `.catch(() => null)` anti-patterns from `nexus/tests/wiki/wiki-edit-consistency.spec.ts` and replaced them with proper Playwright assertions and try/catch blocks.

## Changes Made

### 1. Line 9: `waitForWikiNav()` helper
**Before:**
```typescript
await page.waitForSelector('.wiki-nav, .wiki-sidebar', { timeout: 10000 }).catch(() => null);
```

**After:**
```typescript
await page.waitForSelector('.wiki-nav, .wiki-sidebar', { timeout: 10000 });
```

**Reasoning:** If the wiki nav doesn't load, the test should fail. Silencing errors hides real issues.

---

### 2. Lines 129-132: Article title visibility check
**Before:**
```typescript
const articleTitle = verifiedUser.locator('.article-title .inline-edit-wrapper, .article-title input, .wiki-article h1 .inline-edit-wrapper');
const hasInlineEdit = await articleTitle.isVisible().catch(() => false);

// Weapons page should now have article title inline edit (we fixed it earlier)
expect(hasInlineEdit).toBeTruthy();
```

**After:**
```typescript
const articleTitle = verifiedUser.locator('.article-title .inline-edit-wrapper, .article-title input, .wiki-article h1 .inline-edit-wrapper');
await expect(articleTitle).toBeVisible();
```

**Reasoning:**
- Removed redundant boolean check pattern
- Used direct assertion which provides better error messages
- If element doesn't exist, test fails immediately with clear context

---

### 3. Lines 189-203: Save button visibility checks
**Before:**
```typescript
// At least one save-type button should be visible
const hasSaveDraft = await saveDraftBtn.isVisible().catch(() => false);
const hasSave = await saveBtn.isVisible().catch(() => false);
const hasSubmitReview = await submitReviewBtn.isVisible().catch(() => false);
expect(hasSaveDraft || hasSave || hasSubmitReview).toBeTruthy();
```

**After:**
```typescript
// At least one save-type button should be visible
let hasSaveButton = false;
try {
  await expect(saveDraftBtn).toBeVisible({ timeout: 2000 });
  hasSaveButton = true;
} catch {
  try {
    await expect(saveBtn).toBeVisible({ timeout: 2000 });
    hasSaveButton = true;
  } catch {
    await expect(submitReviewBtn).toBeVisible({ timeout: 2000 });
    hasSaveButton = true;
  }
}
expect(hasSaveButton).toBeTruthy();
```

**Reasoning:**
- Proper try/catch blocks with explicit timeouts
- Each assertion can provide specific error messages
- Still allows fallback logic for multiple button variants
- Better error reporting when ALL buttons are missing

---

### 4. Lines 254-255: Enhancers edit button check
**Before:**
```typescript
const editButton = verifiedUser.locator('button:has-text("Edit")');
const hasEditButton = await editButton.isVisible().catch(() => false);
expect(hasEditButton).toBeFalsy();
```

**After:**
```typescript
const editButton = verifiedUser.locator('button:has-text("Edit")');
await expect(editButton).not.toBeVisible();
```

**Reasoning:**
- Used Playwright's `.not.toBeVisible()` assertion
- More idiomatic and provides better error messages
- Removed redundant boolean intermediate variable

---

## Benefits

1. **Better Error Messages:** Playwright assertions provide stack traces and clear failure reasons
2. **No Hidden Errors:** Strict mode violations and unexpected errors now surface properly
3. **Consistent Patterns:** All checks use proper Playwright assertions
4. **Maintainability:** Code is clearer and easier to understand
5. **Debugging:** When tests fail, we get actionable information instead of silent failures

## Testing Recommendations

Run the full test suite to ensure all changes work correctly:
```bash
npm run test:e2e -- tests/wiki/wiki-edit-consistency.spec.ts
```

If any tests fail, it means they were previously passing due to silenced errors - these need to be fixed in the application code, not the tests.
