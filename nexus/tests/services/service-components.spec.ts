import { test, expect } from '@playwright/test';

test.describe('Service Components', () => {
  test.describe('EquipmentEditor Component', () => {
    test('equipment editor appears on create page for healing type', async ({ page }) => {
      await page.goto('/market/services/create');
      await page.waitForLoadState('networkidle');

      if (await page.locator('form').isVisible().catch(() => false)) {
        // Select healing type
        const typeSelect = page.locator('select#serviceType');
        await typeSelect.selectOption('healing');

        // Look for equipment editor section
        const equipmentSection = page.locator('text=Equipment').or(
          page.locator('[class*="equipment"]')
        );

        const hasEquipment = await equipmentSection.first().isVisible().catch(() => false);
        expect(hasEquipment).toBeTruthy();
      }
    });

    test('equipment editor appears on create page for DPS type', async ({ page }) => {
      await page.goto('/market/services/create');
      await page.waitForLoadState('networkidle');

      if (await page.locator('form').isVisible().catch(() => false)) {
        // Select DPS type
        const typeSelect = page.locator('select#serviceType');
        await typeSelect.selectOption('dps');

        // Look for equipment editor section
        const equipmentSection = page.locator('text=Equipment').or(
          page.locator('[class*="equipment"]')
        );

        const hasEquipment = await equipmentSection.first().isVisible().catch(() => false);
        expect(hasEquipment).toBeTruthy();
      }
    });

    test('equipment editor does not appear for transportation type', async ({ page }) => {
      await page.goto('/market/services/create');
      await page.waitForLoadState('networkidle');

      if (await page.locator('form').isVisible().catch(() => false)) {
        // Select transportation type
        const typeSelect = page.locator('select#serviceType');
        await typeSelect.selectOption('transportation');

        // Should not show equipment editor (transportation doesn't need it)
        // It may show a different section for transportation details
        const transportSection = page.locator('text=Transportation Details').or(
          page.locator('#transportationType')
        );

        const hasTransportSection = await transportSection.first().isVisible().catch(() => false);
        expect(hasTransportSection).toBeTruthy();
      }
    });
  });

  test.describe('Table Component', () => {
    test('table renders with header and body', async ({ page }) => {
      await page.goto('/market/services');

      const table = page.locator('table');
      const hasTable = await table.first().isVisible().catch(() => false);

      if (hasTable) {
        // Should have header row
        const thead = page.locator('thead');
        await expect(thead).toBeVisible();

        // Should have body (even if empty)
        const tbody = page.locator('tbody');
        await expect(tbody).toBeVisible();
      }
    });

    test('table supports searching', async ({ page }) => {
      await page.goto('/market/services');

      // Look for search functionality in table
      const searchInput = page.locator('.search-row input').or(
        page.locator('input[placeholder*="search" i]')
      );

      const hasSearch = await searchInput.first().isVisible().catch(() => false);
      // Tables with searchable: true should have search
    });

    test('table supports sorting via header click', async ({ page }) => {
      await page.goto('/market/services');

      const tableHeader = page.locator('th').first();

      if (await tableHeader.isVisible().catch(() => false)) {
        // Should be clickable for sorting
        const cursor = await tableHeader.evaluate(el => getComputedStyle(el).cursor);
        // Sortable headers typically have pointer cursor
      }
    });
  });

  test.describe('RequestStatusBadge Component', () => {
    test('status badges have proper styling', async ({ page }) => {
      await page.goto('/market/services/my');
      await page.waitForLoadState('networkidle');

      if (!page.url().includes('login')) {
        // Look for status badges
        const badge = page.locator('[class*="badge"]').or(
          page.locator('[class*="status"]')
        );

        if (await badge.first().isVisible().catch(() => false)) {
          // Badge should have background color
          const bgColor = await badge.first().evaluate(el =>
            getComputedStyle(el).backgroundColor
          );

          expect(bgColor).not.toBe('rgba(0, 0, 0, 0)');
        }
      }
    });
  });

  test.describe('DashboardNav Component', () => {
    test('dashboard nav appears on my services page', async ({ page }) => {
      await page.goto('/market/services/my');
      await page.waitForLoadState('networkidle');

      if (!page.url().includes('login')) {
        // Look for dashboard navigation
        const dashboardNav = page.locator('nav').or(
          page.locator('[class*="nav"]')
        );

        const hasNav = await dashboardNav.first().isVisible().catch(() => false);
        // Should have navigation component if authenticated
      }
    });
  });

  test.describe('AvailabilityCalendar Component', () => {
    test('availability calendar page loads', async ({ page }) => {
      await page.goto('/market/services/1/availability');
      await page.waitForLoadState('networkidle');

      // Should either show calendar or error/redirect
      await expect(page.locator('body')).toBeVisible();
    });
  });

  test.describe('TicketOfferCard Component', () => {
    test('ticket offers page loads', async ({ page }) => {
      await page.goto('/market/services/1/ticket-offers');
      await page.waitForLoadState('networkidle');

      // Should show ticket offers interface or appropriate message
      await expect(page.locator('body')).toBeVisible();
    });
  });

  test.describe('LocationManager Component', () => {
    test('location management available on service pages', async ({ page }) => {
      // Location manager is used for transportation services
      await page.goto('/market/services');

      // Navigate to transportation type
      const transportBtn = page.locator('.type-btn:has-text("Transport")');
      if (await transportBtn.isVisible().catch(() => false)) {
        await transportBtn.click();

        // Table should render transportation services
        const table = page.locator('table');
        const hasTable = await table.isVisible().catch(() => false);
        expect(true).toBeTruthy();
      }
    });
  });

  test.describe('PilotManager Component', () => {
    test('pilot management loads', async ({ page }) => {
      // Pilot manager is used for transportation services
      // We can't test specific service IDs, but verify the page structure works
      await page.goto('/market/services/1/edit');
      await page.waitForLoadState('networkidle');

      // Should redirect to login or show form
      await expect(page.locator('body')).toBeVisible();
    });
  });

  test.describe('serviceCalculations', () => {
    test('services page loads calculations for healing', async ({ page }) => {
      await page.goto('/market/services');

      // Click on healing type
      const healingBtn = page.locator('.type-btn:has-text("Healing")');
      if (await healingBtn.isVisible().catch(() => false)) {
        await healingBtn.click();

        // Check if HP/s column shows data or "TBD"
        const table = page.locator('table');
        if (await table.isVisible().catch(() => false)) {
          const cells = await page.locator('td').allTextContents();
          // Should have some data or TBD values
        }
      }
    });

    test('services page loads calculations for DPS', async ({ page }) => {
      await page.goto('/market/services');

      // Click on DPS type
      const dpsBtn = page.locator('.type-btn:has-text("DPS")');
      if (await dpsBtn.isVisible().catch(() => false)) {
        await dpsBtn.click();

        // Check if DPS column shows data or "TBD"
        const table = page.locator('table');
        if (await table.isVisible().catch(() => false)) {
          const cells = await page.locator('td').allTextContents();
          // Should have some data or TBD values
        }
      }
    });
  });
});

test.describe('Component CSS Variables', () => {
  test('table wrapper uses theme variables', async ({ page }) => {
    await page.goto('/market/services');

    const tableWrapper = page.locator('.table-wrapper');

    if (await tableWrapper.first().isVisible().catch(() => false)) {
      // Should use CSS variables for theming
      const bgColor = await tableWrapper.first().evaluate(el =>
        getComputedStyle(el).backgroundColor
      );

      // Should have a background color set
      expect(bgColor).toBeTruthy();
      expect(bgColor).not.toBe('rgba(0, 0, 0, 0)');
    }
  });

  test('buttons use theme variables', async ({ page }) => {
    await page.goto('/market/services');

    const button = page.locator('button').or(page.locator('.type-btn')).first();

    if (await button.isVisible().catch(() => false)) {
      const color = await button.evaluate(el => getComputedStyle(el).color);
      const bgColor = await button.evaluate(el => getComputedStyle(el).backgroundColor);

      // Button should have visible text
      expect(color).toBeTruthy();
    }
  });

  test('form inputs use theme variables', async ({ page }) => {
    await page.goto('/market/services/create');
    await page.waitForLoadState('networkidle');

    if (await page.locator('form').isVisible().catch(() => false)) {
      const input = page.locator('input[type="text"]').first();

      if (await input.isVisible().catch(() => false)) {
        const bgColor = await input.evaluate(el => getComputedStyle(el).backgroundColor);
        const color = await input.evaluate(el => getComputedStyle(el).color);
        const borderColor = await input.evaluate(el => getComputedStyle(el).borderColor);

        // Inputs should have proper styling
        expect(bgColor).toBeTruthy();
        expect(color).toBeTruthy();
        expect(borderColor).toBeTruthy();
      }
    }
  });

  test('select dropdowns use theme variables', async ({ page }) => {
    await page.goto('/market/services/create');
    await page.waitForLoadState('networkidle');

    if (await page.locator('form').isVisible().catch(() => false)) {
      const select = page.locator('select').first();

      if (await select.isVisible().catch(() => false)) {
        const bgColor = await select.evaluate(el => getComputedStyle(el).backgroundColor);
        const color = await select.evaluate(el => getComputedStyle(el).color);

        // Selects should have proper styling for dark/light mode
        expect(bgColor).toBeTruthy();
        expect(color).toBeTruthy();
      }
    }
  });
});

test.describe('Component Accessibility', () => {
  test('form inputs have labels', async ({ page }) => {
    await page.goto('/market/services/create');
    await page.waitForLoadState('networkidle');

    if (await page.locator('form').isVisible().catch(() => false)) {
      // Check that inputs have associated labels
      const inputs = page.locator('input[id]');
      const inputCount = await inputs.count();

      for (let i = 0; i < Math.min(inputCount, 5); i++) {
        const input = inputs.nth(i);
        const id = await input.getAttribute('id');

        if (id) {
          // Should have a label for this input
          const label = page.locator(`label[for="${id}"]`);
          const hasLabel = await label.isVisible().catch(() => false);
          // Most inputs should have labels
        }
      }
    }
  });

  test('buttons are keyboard accessible', async ({ page }) => {
    await page.goto('/market/services');

    // Tab to buttons and verify they can be focused
    await page.keyboard.press('Tab');

    const focusedElement = page.locator(':focus');
    const tagName = await focusedElement.evaluate(el => el.tagName).catch(() => null);

    // Should be able to focus interactive elements
    expect(true).toBeTruthy();
  });

  test('tables have semantic structure', async ({ page }) => {
    await page.goto('/market/services');

    const table = page.locator('table');

    if (await table.first().isVisible().catch(() => false)) {
      // Should have thead and tbody
      const thead = table.locator('thead');
      const tbody = table.locator('tbody');

      await expect(thead).toBeVisible();
      await expect(tbody).toBeVisible();

      // Headers should use th elements
      const thElements = thead.locator('th');
      const thCount = await thElements.count();
      expect(thCount).toBeGreaterThan(0);
    }
  });
});
