import { test, expect } from '../fixtures/auth';
import { TIMEOUT_SHORT, TIMEOUT_MEDIUM, TIMEOUT_LONG } from '../test-constants';

/**
 * Tests for the map editor snap functionality:
 * - Snap toolbar UI (Snap Edges, Snap Grid, Gap input)
 * - computeSnapOffset algorithm (alignment guards, gap sizes, threshold)
 * - computeVertexSnap algorithm (vertex-to-vertex, gap-offset, grid lines)
 * - getShapeVertices extraction
 * - getShapeBounds computation
 */

// ─── Helper: load the snap utility module in browser context ─────────────────

/**
 * Evaluate a function that imports mapEditorUtils and runs snap logic.
 * The module is loaded dynamically inside the browser to access the actual code.
 */
async function evalSnapUtil(page: any, fn: string) {
  return page.evaluate(fn);
}

// ─── Snap Toolbar UI Tests ──────────────────────────────────────────────────

test.describe('Map Editor Snap - Toolbar UI', () => {
  test.beforeEach(async ({ adminUser }) => {
    await adminUser.goto('/admin/map');
    await adminUser.waitForLoadState('networkidle');
    await expect(adminUser.locator('.admin-map-page')).toBeVisible({ timeout: TIMEOUT_MEDIUM });
  });

  test('snap toolbar is hidden in view mode', async ({ adminUser }) => {
    const snapToolbar = adminUser.locator('.snap-toolbar');
    await expect(snapToolbar).toBeHidden();
  });

  test('snap toolbar appears in edit mode', async ({ adminUser }) => {
    // Switch to edit mode
    const editBtn = adminUser.locator('.mode-toggle button', { hasText: 'Edit' });
    await editBtn.click();

    // Select a planet to load the map
    const planetSelect = adminUser.locator('.toolbar select');
    const options = await planetSelect.locator('option:not([disabled])').all();
    if (options.length > 0) {
      const value = await options[0].getAttribute('value');
      if (value) await planetSelect.selectOption(value);
    }
    await adminUser.waitForTimeout(TIMEOUT_MEDIUM);

    const snapToolbar = adminUser.locator('.snap-toolbar');
    await expect(snapToolbar).toBeVisible({ timeout: TIMEOUT_LONG });
  });

  test('snap toolbar has all controls', async ({ adminUser }) => {
    const editBtn = adminUser.locator('.mode-toggle button', { hasText: 'Edit' });
    await editBtn.click();

    const planetSelect = adminUser.locator('.toolbar select');
    const options = await planetSelect.locator('option:not([disabled])').all();
    if (options.length > 0) {
      const value = await options[0].getAttribute('value');
      if (value) await planetSelect.selectOption(value);
    }
    await adminUser.waitForTimeout(TIMEOUT_MEDIUM);

    const snapToolbar = adminUser.locator('.snap-toolbar');
    await expect(snapToolbar).toBeVisible({ timeout: TIMEOUT_LONG });

    // Snap Edges button
    const snapEdgesBtn = snapToolbar.locator('button', { hasText: 'Snap Edges' });
    await expect(snapEdgesBtn).toBeVisible();

    // Snap Grid button
    const snapGridBtn = snapToolbar.locator('button', { hasText: 'Snap Grid' });
    await expect(snapGridBtn).toBeVisible();

    // Hint text
    const hint = snapToolbar.locator('.snap-hint');
    await expect(hint).toContainText('Shift+drag vertex');
  });

  test('gap input toggles with Snap Edges button', async ({ adminUser }) => {
    const editBtn = adminUser.locator('.mode-toggle button', { hasText: 'Edit' });
    await editBtn.click();

    const planetSelect = adminUser.locator('.toolbar select');
    const options = await planetSelect.locator('option:not([disabled])').all();
    if (options.length > 0) {
      const value = await options[0].getAttribute('value');
      if (value) await planetSelect.selectOption(value);
    }
    await adminUser.waitForTimeout(TIMEOUT_MEDIUM);

    const snapToolbar = adminUser.locator('.snap-toolbar');
    await expect(snapToolbar).toBeVisible({ timeout: TIMEOUT_LONG });

    // Snap Edges enabled by default → gap input visible with value 5
    const snapEdgesBtn = snapToolbar.locator('button', { hasText: 'Snap Edges' });
    const gapInput = snapToolbar.locator('.snap-gap-input');
    await expect(snapEdgesBtn).toHaveClass(/active/, { timeout: TIMEOUT_SHORT });
    await expect(gapInput).toBeVisible({ timeout: TIMEOUT_SHORT });
    await expect(gapInput).toHaveValue('5');

    // Toggle off → gap input hidden
    await snapEdgesBtn.click();
    await expect(gapInput).toBeHidden({ timeout: TIMEOUT_SHORT });

    // Toggle back on → gap input visible again
    await snapEdgesBtn.click();
    await expect(gapInput).toBeVisible({ timeout: TIMEOUT_SHORT });
  });

  test('Snap Grid button toggles active state', async ({ adminUser }) => {
    const editBtn = adminUser.locator('.mode-toggle button', { hasText: 'Edit' });
    await editBtn.click();

    const planetSelect = adminUser.locator('.toolbar select');
    const options = await planetSelect.locator('option:not([disabled])').all();
    if (options.length > 0) {
      const value = await options[0].getAttribute('value');
      if (value) await planetSelect.selectOption(value);
    }
    await adminUser.waitForTimeout(TIMEOUT_MEDIUM);

    const snapToolbar = adminUser.locator('.snap-toolbar');
    await expect(snapToolbar).toBeVisible({ timeout: TIMEOUT_LONG });

    const snapGridBtn = snapToolbar.locator('button', { hasText: 'Snap Grid' });

    // Initially active (enabled by default)
    await expect(snapGridBtn).toHaveClass(/active/, { timeout: TIMEOUT_SHORT });

    // Click to deactivate
    await snapGridBtn.click();
    await expect(snapGridBtn).not.toHaveClass(/active/, { timeout: TIMEOUT_SHORT });

    // Click to reactivate
    await snapGridBtn.click();
    await expect(snapGridBtn).toHaveClass(/active/, { timeout: TIMEOUT_SHORT });
  });
});

// ─── computeSnapOffset Algorithm Tests ──────────────────────────────────────

test.describe('Map Editor Snap - computeSnapOffset Algorithm', () => {
  // We load any page and dynamically import the utility module for pure algorithm testing
  test.beforeEach(async ({ adminUser }) => {
    await adminUser.goto('/admin/map');
    await adminUser.waitForLoadState('networkidle');
  });

  test('adjacent snap creates correct gap between shapes', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');
      const bounds = { minX: 100, maxX: 200, minY: 100, maxY: 200 };
      const candidate = { minX: 300, maxX: 400, minY: 100, maxY: 200 };
      const results = [];

      // Test gap sizes: 0, 5, 10, 50, 100
      for (const gap of [0, 5, 10, 50, 100]) {
        const snap = mod.computeSnapOffset(bounds, [candidate], null, gap, 500);
        results.push({ gap, dx: snap.dx, dy: snap.dy });
      }
      return results;
    });

    // bounds.maxX=200, candidate.minX=300, so distance is 100
    // With gap=0: snap A.maxX to B.minX → dx = 300 - 0 - 200 = 100
    // With gap=5: dx = 300 - 5 - 200 = 95
    // With gap=10: dx = 300 - 10 - 200 = 90
    // With gap=50: dx = 300 - 50 - 200 = 50
    // With gap=100: dx = 300 - 100 - 200 = 0 (already at gap distance)
    expect(result[0]).toEqual({ gap: 0, dx: 100, dy: 0 });
    expect(result[1]).toEqual({ gap: 5, dx: 95, dy: 0 });
    expect(result[2]).toEqual({ gap: 10, dx: 90, dy: 0 });
    expect(result[3]).toEqual({ gap: 50, dx: 50, dy: 0 });
    expect(result[4]).toEqual({ gap: 100, dx: 0, dy: 0 });
  });

  test('alignment pairings only fire when shapes are separated on perpendicular axis', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      // Case 1: Shapes overlap on Y (same vertical extent) — alignment on X should NOT fire
      const boundsOverlapY = { minX: 100, maxX: 200, minY: 100, maxY: 300 };
      const candidateOverlapY = { minX: 300, maxX: 500, minY: 150, maxY: 250 };
      // A.maxX (200) is 100 away from align target B.maxX (500) = corr 300
      // A.maxX (200) is 100 away from adjacent B.minX (300) with gap=0 → corr 100
      // Adjacent should win (smaller correction)
      const snap1 = mod.computeSnapOffset(boundsOverlapY, [candidateOverlapY], null, 0, 500);

      // Case 2: Shapes separated on Y (stacked) — alignment on X SHOULD fire
      const boundsSepY = { minX: 100, maxX: 200, minY: 500, maxY: 600 };
      const candidateSepY = { minX: 300, maxX: 500, minY: 100, maxY: 200 };
      // Separated on Y (bounds.minY=500 > candidate.maxY=200)
      // Adjacent: B.minX - 0 - A.maxX = 300 - 200 = 100
      // Alignment: B.minX - A.minX = 300 - 100 = 200, or B.maxX - A.maxX = 500 - 200 = 300
      // Adjacent wins (100 < 200)
      const snap2 = mod.computeSnapOffset(boundsSepY, [candidateSepY], null, 0, 500);

      // Case 3: Shapes overlap on Y, close to alignment — should NOT snap to alignment
      const boundsClose = { minX: 498, maxX: 600, minY: 100, maxY: 300 };
      const candidateClose = { minX: 300, maxX: 500, minY: 150, maxY: 250 };
      // Adjacent: B.maxX + 0 - A.minX = 500 + 0 - 498 = 2 → small adjacent correction
      // Alignment: B.maxX - A.maxX = 500 - 600 = -100
      // A.minX - B.minX = 300 - 498 = -198
      // Adjacent (2) should win, and alignment should be blocked
      const snap3 = mod.computeSnapOffset(boundsClose, [candidateClose], null, 0, 500);

      return { snap1, snap2, snap3 };
    });

    // Case 1: Adjacent should fire (dx=100), not alignment
    expect(result.snap1.dx).toBe(100);

    // Case 2: Adjacent still wins (100 is smallest)
    expect(result.snap2.dx).toBe(100);

    // Case 3: Adjacent fires (dx=2), alignment blocked since overlapping on Y
    expect(result.snap3.dx).toBe(2);
  });

  test('alignment does NOT pull shapes inside each other', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      // Shape A is close to shape B, overlapping on Y
      // Without the separation guard, alignment (A.maxX → B.maxX) would pull A into B
      const bounds = { minX: 150, maxX: 250, minY: 100, maxY: 300 };
      const candidate = { minX: 200, maxX: 400, minY: 100, maxY: 300 };
      // Overlapping on Y (same range), overlapping on X partially

      // Alignment: B.maxX - A.maxX = 400 - 250 = 150 (would push A right INTO B)
      // Alignment: B.minX - A.minX = 200 - 150 = 50 (would push A right INTO B)
      // Adjacent: B.minX - 0 - A.maxX = 200 - 250 = -50 (push A left, create gap)
      // Adjacent: B.maxX + 0 - A.minX = 400 - 150 = 250 (push A right past B)
      const snap = mod.computeSnapOffset(bounds, [candidate], null, 0, 500);

      // After snap, verify no overlap would occur
      const newMinX = bounds.minX + snap.dx;
      const newMaxX = bounds.maxX + snap.dx;
      const wouldOverlap = newMaxX > candidate.minX && newMinX < candidate.maxX;

      return { snap, wouldOverlap, newMinX, newMaxX };
    });

    // Should choose adjacent snap that pushes A to the left (dx=-50)
    expect(result.snap.dx).toBe(-50);
    // After snap: A = [100, 200], B = [200, 400] — touching but not overlapping
    expect(result.wouldOverlap).toBe(false);
  });

  test('snaps to both X and Y independently for corner alignment', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      // Shape A is near the top-right corner of shape B
      const bounds = { minX: 495, maxX: 600, minY: 10, maxY: 90 };
      const candidate = { minX: 100, maxX: 500, minY: 100, maxY: 400 };

      // X: A.minX (495) close to B.maxX (500) + gap → adjacent snap
      // Y: A.maxY (90) close to B.minY (100) - gap → adjacent snap
      const results = [];
      for (const gap of [0, 5, 10]) {
        const snap = mod.computeSnapOffset(bounds, [candidate], null, gap, 500);
        results.push({ gap, dx: snap.dx, dy: snap.dy });
      }
      return results;
    });

    // gap=0: dx = 500 + 0 - 495 = 5, dy = 100 - 0 - 90 = 10
    expect(result[0].dx).toBe(5);
    expect(result[0].dy).toBe(10);

    // gap=5: dx = 500 + 5 - 495 = 10, dy = 100 - 5 - 90 = 5
    expect(result[1].dx).toBe(10);
    expect(result[1].dy).toBe(5);

    // gap=10: dx = 500 + 10 - 495 = 15, dy = 100 - 10 - 90 = 0
    expect(result[2].dx).toBe(15);
    expect(result[2].dy).toBe(0);
  });

  test('grid line snapping works at various positions', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      const gridLines = {
        xLines: [16384, 24576, 32768], // 2*8192, 3*8192, 4*8192
        yLines: [24576, 32768, 40960],
      };
      const results = [];

      // Shape near a grid line
      const bounds1 = { minX: 16300, maxX: 16500, minY: 24500, maxY: 24700 };
      results.push(mod.computeSnapOffset(bounds1, [], gridLines, 0, 500));

      // Shape exactly on a grid line (no correction needed)
      const bounds2 = { minX: 16384, maxX: 16600, minY: 24576, maxY: 24800 };
      results.push(mod.computeSnapOffset(bounds2, [], gridLines, 0, 500));

      // Shape far from any grid line (beyond threshold)
      const bounds3 = { minX: 20000, maxX: 20200, minY: 28000, maxY: 28200 };
      results.push(mod.computeSnapOffset(bounds3, [], gridLines, 0, 500));

      return results;
    });

    // Near grid: minX=16300 → grid 16384, correction = 84
    expect(result[0].dx).toBe(84);
    // Near grid: minY=24500 → grid 24576, correction = 76
    expect(result[0].dy).toBe(76);

    // On grid: no correction
    expect(result[1].dx).toBe(0);
    expect(result[1].dy).toBe(0);

    // Far: 20000 is 3616 from 16384 and 4576 from 24576, both > 500 threshold
    expect(result[2].dx).toBe(0);
    expect(result[2].dy).toBe(0);
  });

  test('candidate snap takes priority over grid when closer', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      const bounds = { minX: 16350, maxX: 16500, minY: 100, maxY: 200 };
      const candidate = { minX: 16510, maxX: 16700, minY: 100, maxY: 200 };
      const gridLines = { xLines: [16384], yLines: [] };

      // Adjacent: B.minX - gap - A.maxX = 16510 - 0 - 16500 = 10
      // Grid: 16384 - A.minX = 16384 - 16350 = 34, or 16384 - A.maxX = 16384 - 16500 = -116
      // Adjacent (10) wins over grid (34)
      const snap = mod.computeSnapOffset(bounds, [candidate], gridLines, 0, 500);
      return snap;
    });

    expect(result.dx).toBe(10);
  });

  test('snap works with various gap sizes', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      // Two shapes 100 units apart
      const bounds = { minX: 100, maxX: 200, minY: 0, maxY: 100 };
      const candidate = { minX: 300, maxX: 400, minY: 0, maxY: 100 };
      const results = [];

      // Test many gap sizes
      for (const gap of [0, 1, 5, 10, 25, 50, 100, 200]) {
        const snap = mod.computeSnapOffset(bounds, [candidate], null, gap, 500);
        // After snap: A.maxX + dx should be at B.minX - gap
        const finalMaxX = bounds.maxX + snap.dx;
        results.push({ gap, dx: snap.dx, finalMaxX, expectedMaxX: candidate.minX - gap });
      }
      return results;
    });

    for (const r of result) {
      expect(r.finalMaxX).toBe(r.expectedMaxX);
    }
  });

  test('distant candidates are ignored by edge proximity filter (Euclidean)', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      const threshold = 200; // proximity = 400
      const bounds = { minX: 1000, maxX: 1100, minY: 1000, maxY: 1100 };

      // Candidate far on both axes — Euclidean dist ~5515, skipped
      const far = { minX: 5000, maxX: 5100, minY: 5000, maxY: 5100 };
      const snap1 = mod.computeSnapOffset(bounds, [far], null, 0, threshold);

      // Candidate close on X but far on Y — Euclidean dist ~3901, skipped
      const farY = { minX: 1200, maxX: 1300, minY: 5000, maxY: 5100 };
      const snap2 = mod.computeSnapOffset(bounds, [farY], null, 0, threshold);

      // Candidate nearby — Euclidean dist = 100 (X gap only), within proximity
      const near = { minX: 1200, maxX: 1300, minY: 1000, maxY: 1100 };
      const snap3 = mod.computeSnapOffset(bounds, [near], null, 0, threshold);

      // Candidate diagonally nearby — xGap=100, yGap=100, dist=~141, within proximity
      const diag = { minX: 1200, maxX: 1300, minY: 1200, maxY: 1300 };
      const snap4 = mod.computeSnapOffset(bounds, [diag], null, 0, threshold);

      return { snap1, snap2, snap3, snap4 };
    });

    // Far on both: no snap
    expect(result.snap1.dx).toBe(0);
    expect(result.snap1.dy).toBe(0);

    // Close on X, far on Y: Euclidean too far, no snap
    expect(result.snap2.dx).toBe(0);
    expect(result.snap2.dy).toBe(0);

    // Nearby on X: snaps
    expect(result.snap3.dx).toBe(100);

    // Diagonally nearby: snaps on both axes
    expect(result.snap4.dx).toBe(100);
    expect(result.snap4.dy).toBe(100);
  });
});

// ─── computeVertexSnap Algorithm Tests ──────────────────────────────────────

test.describe('Map Editor Snap - computeVertexSnap Algorithm', () => {
  test.beforeEach(async ({ adminUser }) => {
    await adminUser.goto('/admin/map');
    await adminUser.waitForLoadState('networkidle');
  });

  test('vertex snaps exactly to candidate vertex (gap=0)', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      const candidateVertices = [
        { x: 1000, y: 2000 },
        { x: 3000, y: 4000 },
      ];

      // Vertex near first candidate
      const snap1 = mod.computeVertexSnap(1010, 1990, candidateVertices, null, 0, 500);
      // Vertex near second candidate
      const snap2 = mod.computeVertexSnap(3005, 4008, candidateVertices, null, 0, 500);
      // Vertex far from any candidate (beyond threshold)
      const snap3 = mod.computeVertexSnap(5000, 5000, candidateVertices, null, 0, 500);

      return { snap1, snap2, snap3 };
    });

    // Near (1000, 2000): dx = -10, dy = 10
    expect(result.snap1.dx).toBe(-10);
    expect(result.snap1.dy).toBe(10);
    // matchX/matchY should reference the candidate vertex that triggered the snap
    expect(result.snap1.matchX).toEqual(expect.objectContaining({ x: 1000, y: 2000 }));
    expect(result.snap1.matchY).toEqual(expect.objectContaining({ x: 1000, y: 2000 }));

    // Near (3000, 4000): dx = -5, dy = -8
    expect(result.snap2.dx).toBe(-5);
    expect(result.snap2.dy).toBe(-8);
    expect(result.snap2.matchX).toEqual(expect.objectContaining({ x: 3000, y: 4000 }));
    expect(result.snap2.matchY).toEqual(expect.objectContaining({ x: 3000, y: 4000 }));

    // Far: no snap — matchX/matchY should be null
    expect(result.snap3.dx).toBe(0);
    expect(result.snap3.dy).toBe(0);
    expect(result.snap3.matchX).toBeNull();
    expect(result.snap3.matchY).toBeNull();
  });

  test('vertex snaps with gap offset at different gap sizes', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      const candidateVertices = [{ x: 1000, y: 2000 }];
      const results = [];

      // Vertex approaching from the right side (vx > cv.x)
      for (const gap of [5, 10, 50, 100]) {
        const snap = mod.computeVertexSnap(1000 + gap + 3, 2000, candidateVertices, null, gap, 500);
        results.push({
          gap,
          dx: snap.dx,
          finalX: 1000 + gap + 3 + snap.dx,
          expectedX: 1000 + gap, // Should snap to cv.x + gap
        });
      }
      return results;
    });

    for (const r of result) {
      expect(r.finalX).toBe(r.expectedX);
    }
  });

  test('vertex gap snap respects direction (sign)', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      const candidateVertices = [{ x: 1000, y: 2000 }];
      const gap = 20;

      // Approaching from right (vx > cv.x) → snaps to cv.x + gap = 1020
      const snapRight = mod.computeVertexSnap(1025, 2000, candidateVertices, null, gap, 500);
      // Approaching from left (vx < cv.x) → snaps to cv.x - gap = 980
      const snapLeft = mod.computeVertexSnap(975, 2000, candidateVertices, null, gap, 500);
      // Approaching from above (vy > cv.y) → snaps to cv.y + gap = 2020
      const snapAbove = mod.computeVertexSnap(1000, 2025, candidateVertices, null, gap, 500);
      // Approaching from below (vy < cv.y) → snaps to cv.y - gap = 1980
      const snapBelow = mod.computeVertexSnap(1000, 1975, candidateVertices, null, gap, 500);

      return {
        fromRight: { dx: snapRight.dx, finalX: 1025 + snapRight.dx },
        fromLeft: { dx: snapLeft.dx, finalX: 975 + snapLeft.dx },
        fromAbove: { dy: snapAbove.dy, finalY: 2025 + snapAbove.dy },
        fromBelow: { dy: snapBelow.dy, finalY: 1975 + snapBelow.dy },
      };
    });

    expect(result.fromRight.finalX).toBe(1020); // cv.x + gap
    expect(result.fromLeft.finalX).toBe(980);   // cv.x - gap
    expect(result.fromAbove.finalY).toBe(2020); // cv.y + gap
    expect(result.fromBelow.finalY).toBe(1980); // cv.y - gap
  });

  test('vertex snaps to both X and Y independently for corner alignment', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      // Two candidate vertices forming a corner
      const candidateVertices = [
        { x: 1000, y: 2000 },
        { x: 1000, y: 3000 },
        { x: 2000, y: 2000 },
      ];

      // Vertex near corner — should snap X to 1000, Y to 2000
      const snap = mod.computeVertexSnap(1008, 1995, candidateVertices, null, 0, 500);
      return { dx: snap.dx, dy: snap.dy, finalX: 1008 + snap.dx, finalY: 1995 + snap.dy };
    });

    expect(result.finalX).toBe(1000);
    expect(result.finalY).toBe(2000);
  });

  test('vertex snaps to grid lines', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      const gridLines = {
        xLines: [16384, 24576],
        yLines: [24576, 32768],
      };

      // Near grid intersection
      const snap1 = mod.computeVertexSnap(16390, 24580, [], gridLines, 0, 500);
      // Far from grid
      const snap2 = mod.computeVertexSnap(20000, 28000, [], gridLines, 0, 500);
      // Near one grid line on X only
      const snap3 = mod.computeVertexSnap(24570, 28000, [], gridLines, 0, 500);

      return { snap1, snap2, snap3 };
    });

    // Near grid intersection: dx = 16384 - 16390 = -6, dy = 24576 - 24580 = -4
    expect(result.snap1.dx).toBe(-6);
    expect(result.snap1.dy).toBe(-4);

    // Far: no snap
    expect(result.snap2.dx).toBe(0);
    expect(result.snap2.dy).toBe(0);

    // Near X grid only: dx = 24576 - 24570 = 6, dy = 0
    expect(result.snap3.dx).toBe(6);
    expect(result.snap3.dy).toBe(0);
  });

  test('exact vertex match takes priority over gap-offset when closer', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      // Candidate at (1000, 2000), gap = 50
      // Vertex at (1002, 2000) — exact match is 2 away, gap-offset (1050) is 48 away
      const candidateVertices = [{ x: 1000, y: 2000 }];
      const snap = mod.computeVertexSnap(1002, 2000, candidateVertices, null, 50, 500);
      return { dx: snap.dx, finalX: 1002 + snap.dx };
    });

    // Exact match (distance 2) wins over gap-offset (distance 48)
    expect(result.finalX).toBe(1000);
  });

  test('matchX and matchY track different candidate vertices for independent axis snaps', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      // Two nearby candidate vertices: one closer on X, another closer on Y
      // Vertex at (1005, 1003), threshold=100, proximity=200
      const candidateVertices = [
        { x: 1000, y: 1100 }, // closer on X (dx=-5), Y distance=97 (within proximity)
        { x: 1080, y: 1000 }, // closer on Y (dy=-3), X distance=75 (within proximity)
      ];
      const snap = mod.computeVertexSnap(1005, 1003, candidateVertices, null, 0, 100);
      return snap;
    });

    // X should snap to first candidate (dx=-5), Y to second (dy=-3)
    expect(result.dx).toBe(-5);
    expect(result.dy).toBe(-3);
    expect(result.matchX).toEqual(expect.objectContaining({ x: 1000, y: 1100 }));
    expect(result.matchY).toEqual(expect.objectContaining({ x: 1080, y: 1000 }));
  });

  test('grid snap sets matchX/matchY to null', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      const gridLines = { xLines: [16384], yLines: [24576] };
      // Vertex near grid, no candidate vertices
      const snap = mod.computeVertexSnap(16390, 24580, [], gridLines, 0, 500);
      return snap;
    });

    expect(result.dx).toBe(-6);
    expect(result.dy).toBe(-4);
    // Grid snaps should have null matchX/matchY (no specific vertex to highlight)
    expect(result.matchX).toBeNull();
    expect(result.matchY).toBeNull();
  });

  test('distant vertices are ignored by proximity filter (Euclidean)', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      const threshold = 100; // proximity = 200, proximitySq = 40000

      // Vertex at (1000, 1000). Candidate far away — Euclidean dist ~5657, skipped
      const farBoth = [{ x: 5000, y: 5000 }];
      const snap1 = mod.computeVertexSnap(1000, 1000, farBoth, null, 0, threshold);

      // Candidate far on Y only — Euclidean dist ~49000, skipped
      const farY = [{ x: 1005, y: 50000 }];
      const snap2 = mod.computeVertexSnap(1000, 1000, farY, null, 0, threshold);

      // Candidate far on X only — Euclidean dist ~49000, skipped
      const farX = [{ x: 50000, y: 1005 }];
      const snap3 = mod.computeVertexSnap(1000, 1000, farX, null, 0, threshold);

      // Nearby candidate — Euclidean dist ~54, well within proximity
      const nearby = [{ x: 1050, y: 1020 }];
      const snap4 = mod.computeVertexSnap(1000, 1000, nearby, null, 0, threshold);

      // Candidate at (1140, 1140): dist = sqrt(140^2+140^2) ≈ 198 < 200 → included
      const insideCircle = [{ x: 1140, y: 1140 }];
      const snap5 = mod.computeVertexSnap(1000, 1000, insideCircle, null, 0, threshold);

      // Candidate at (1142, 1142): dist = sqrt(142^2+142^2) ≈ 201 > 200 → skipped
      const outsideCircle = [{ x: 1142, y: 1142 }];
      const snap6 = mod.computeVertexSnap(1000, 1000, outsideCircle, null, 0, threshold);

      return { snap1, snap2, snap3, snap4, snap5, snap6 };
    });

    // Far on both axes: no snap
    expect(result.snap1.dx).toBe(0);
    expect(result.snap1.dy).toBe(0);

    // Far on Y, close on X: skipped — prevents cross-map snapping
    expect(result.snap2.dx).toBe(0);
    expect(result.snap2.dy).toBe(0);

    // Far on X, close on Y: skipped
    expect(result.snap3.dx).toBe(0);
    expect(result.snap3.dy).toBe(0);

    // Nearby: snaps on both axes
    expect(result.snap4.dx).toBe(50);
    expect(result.snap4.dy).toBe(20);

    // Inside Euclidean circle but correction > threshold on each axis: no snap
    // (140 > 100 threshold on each axis individually)
    expect(result.snap5.dx).toBe(0);
    expect(result.snap5.dy).toBe(0);

    // Outside Euclidean circle: filtered out entirely
    expect(result.snap6.dx).toBe(0);
    expect(result.snap6.dy).toBe(0);
  });

  test('vertex match has priority over grid — grid must be 2x closer to win', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      const candidateVertices = [{ x: 16400, y: 24600 }];
      const gridLines = { xLines: [16384], yLines: [24576] };

      // vx=16390: vertex dx=10, grid dx=6. Grid needs < 10*0.5=5 to win → 6 > 5, vertex wins.
      // vy=24580: vertex dy=20, grid dy=4. Grid needs < 20*0.5=10 to win → 4 < 10, grid wins.
      const snap1 = mod.computeVertexSnap(16390, 24580, candidateVertices, gridLines, 0, 500);

      // Case where grid is exactly 2x closer: grid at 5 vs vertex at 10.
      // Grid needs < 10*0.5=5. Grid=5, NOT < 5 (equal). Vertex still wins.
      const snap2 = mod.computeVertexSnap(16394, 24580, candidateVertices, gridLines, 0, 500);
      // vx=16394: vertex dx=6, grid dx=10. Vertex is closer, vertex wins outright.
      // Let me pick a better example: vertex at 20, grid at 10 → grid needs <10, grid=10 → no.
      // vx=16380: vertex=16400 → dx=20, grid=16384 → dx=4. Grid needs < 20*0.5=10. 4 < 10 → grid wins.
      const snap3 = mod.computeVertexSnap(16380, 24580, candidateVertices, gridLines, 0, 500);

      // No vertex match — grid snaps normally without the 2x hurdle
      const snap4 = mod.computeVertexSnap(16390, 24580, [], gridLines, 0, 500);

      return { snap1, snap2, snap3, snap4 };
    });

    // Case 1: vertex wins on X (grid not 2x closer), grid wins on Y (4 < 20*0.5=10)
    expect(result.snap1.dx).toBe(10);   // vertex
    expect(result.snap1.matchX).not.toBeNull();
    expect(result.snap1.dy).toBe(-4);   // grid
    expect(result.snap1.matchY).toBeNull();

    // Case 2: vertex is closer on X (6 < 10), vertex wins
    expect(result.snap2.dx).toBe(6);
    expect(result.snap2.matchX).not.toBeNull();

    // Case 3: grid is much closer (4 vs 20), grid wins on X
    expect(result.snap3.dx).toBe(4);
    expect(result.snap3.matchX).toBeNull();

    // Case 4: no vertex candidates, grid snaps normally
    expect(result.snap4.dx).toBe(-6);
    expect(result.snap4.matchX).toBeNull();
  });
});

// ─── getShapeVertices Tests ─────────────────────────────────────────────────

test.describe('Map Editor Snap - getShapeVertices', () => {
  test.beforeEach(async ({ adminUser }) => {
    await adminUser.goto('/admin/map');
    await adminUser.waitForLoadState('networkidle');
  });

  test('extracts rectangle vertices with neighbor info', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');
      const loc = {
        Properties: {
          Shape: 'Rectangle',
          Data: { x: 100, y: 200, width: 300, height: 150 },
        },
      };
      return mod.getShapeVertices(loc);
    });

    expect(result).toHaveLength(4);
    // Check coordinates
    expect(result).toContainEqual(expect.objectContaining({ x: 100, y: 200 }));
    expect(result).toContainEqual(expect.objectContaining({ x: 400, y: 200 }));
    expect(result).toContainEqual(expect.objectContaining({ x: 400, y: 350 }));
    expect(result).toContainEqual(expect.objectContaining({ x: 100, y: 350 }));

    // Verify neighbor info on first vertex (100,200): prev=(100,350), next=(400,200)
    const v0 = result[0];
    expect(v0.prevX).toBe(100);
    expect(v0.prevY).toBe(350);
    expect(v0.nextX).toBe(400);
    expect(v0.nextY).toBe(200);
  });

  test('extracts polygon vertices with neighbor info', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');
      const loc = {
        Properties: {
          Shape: 'Polygon',
          Data: { vertices: [100, 200, 300, 200, 300, 400, 200, 400, 100, 300] },
        },
      };
      return mod.getShapeVertices(loc);
    });

    expect(result).toHaveLength(5);
    expect(result[0]).toEqual(expect.objectContaining({ x: 100, y: 200 }));
    expect(result[1]).toEqual(expect.objectContaining({ x: 300, y: 200 }));
    expect(result[4]).toEqual(expect.objectContaining({ x: 100, y: 300 }));

    // Verify neighbor info: vertex 0 (100,200) has prev=(100,300) [last vertex], next=(300,200)
    expect(result[0].prevX).toBe(100);
    expect(result[0].prevY).toBe(300);
    expect(result[0].nextX).toBe(300);
    expect(result[0].nextY).toBe(200);
  });

  test('returns empty array for circles', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');
      const loc = {
        Properties: {
          Shape: 'Circle',
          Data: { x: 100, y: 200, radius: 50 },
        },
      };
      return mod.getShapeVertices(loc);
    });

    expect(result).toHaveLength(0);
  });

  test('returns empty array for invalid shapes', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');
      return [
        mod.getShapeVertices(null),
        mod.getShapeVertices({}),
        mod.getShapeVertices({ Properties: {} }),
        mod.getShapeVertices({ Properties: { Shape: 'Polygon', Data: { vertices: [1, 2] } } }), // too few
      ];
    });

    for (const r of result) {
      expect(r).toHaveLength(0);
    }
  });
});

// ─── getShapeBounds Tests ───────────────────────────────────────────────────

test.describe('Map Editor Snap - getShapeBounds', () => {
  test.beforeEach(async ({ adminUser }) => {
    await adminUser.goto('/admin/map');
    await adminUser.waitForLoadState('networkidle');
  });

  test('computes circle bounds', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');
      return mod.getShapeBounds({
        Properties: { Shape: 'Circle', Data: { x: 500, y: 300, radius: 100 } },
      });
    });

    expect(result).toEqual({ minX: 400, maxX: 600, minY: 200, maxY: 400 });
  });

  test('computes rectangle bounds', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');
      return mod.getShapeBounds({
        Properties: { Shape: 'Rectangle', Data: { x: 100, y: 200, width: 300, height: 150 } },
      });
    });

    expect(result).toEqual({ minX: 100, maxX: 400, minY: 200, maxY: 350 });
  });

  test('computes polygon bounds', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');
      return mod.getShapeBounds({
        Properties: { Shape: 'Polygon', Data: { vertices: [10, 20, 50, 80, 30, 60] } },
      });
    });

    expect(result).toEqual({ minX: 10, maxX: 50, minY: 20, maxY: 80 });
  });
});

// ─── Threshold Behavior at Different Zoom Levels ────────────────────────────

test.describe('Map Editor Snap - Threshold at Different Zoom Levels', () => {
  test.beforeEach(async ({ adminUser }) => {
    await adminUser.goto('/admin/map');
    await adminUser.waitForLoadState('networkidle');
  });

  test('whole-shape snap threshold is clamped between 200 EU floor and 500 EU ceiling', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const { SNAP_THRESHOLD_PX, SNAP_THRESHOLD_MAX_EU } = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      // Simulate getSnapThreshold at different zoom levels
      // ratio = 8192 / imageTileSize, for a 4096px wide map with 8 tiles: ratio ≈ 16
      const ratio = 16;
      const results = [];

      for (const zoom of [-2, -1, 0, 1, 2, 3, 4, 5]) {
        const scale = Math.pow(2, zoom); // CRS.Simple scale
        const pixelBased = SNAP_THRESHOLD_PX * ratio / scale;
        const shapeThreshold = Math.min(SNAP_THRESHOLD_MAX_EU, Math.max(200, pixelBased));
        results.push({ zoom, pixelBased: Math.round(pixelBased), shapeThreshold: Math.round(shapeThreshold) });
      }
      return results;
    });

    // Whole-shape threshold: always between 200 and 500
    for (const r of result) {
      expect(r.shapeThreshold).toBeGreaterThanOrEqual(200);
      expect(r.shapeThreshold).toBeLessThanOrEqual(500);
    }

    // At low zoom, pixelBased exceeds ceiling but threshold is capped at 500
    expect(result[0].pixelBased).toBeGreaterThan(500); // zoom -2: 25*16/0.25 = 1600
    expect(result[0].shapeThreshold).toBe(500);

    // At high zoom, pixelBased drops below 200 but threshold stays at 200
    const highZoom = result.find(r => r.zoom === 5);
    expect(highZoom!.pixelBased).toBeLessThan(200);
    expect(highZoom!.shapeThreshold).toBe(200);
  });

  test('vertex snap threshold is clamped between 15 EU floor and 100 EU ceiling', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const { VERTEX_SNAP_THRESHOLD_PX, VERTEX_SNAP_THRESHOLD_MAX_EU } = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      const ratio = 16;
      const results = [];

      for (const zoom of [-2, -1, 0, 1, 2, 3, 4, 5]) {
        const scale = Math.pow(2, zoom);
        const pixelBased = VERTEX_SNAP_THRESHOLD_PX * ratio / scale;
        const vertexThreshold = Math.min(VERTEX_SNAP_THRESHOLD_MAX_EU, Math.max(15, pixelBased));
        results.push({ zoom, pixelBased: Math.round(pixelBased), vertexThreshold: Math.round(vertexThreshold) });
      }
      return results;
    });

    // Vertex threshold: always between 15 and 100
    for (const r of result) {
      expect(r.vertexThreshold).toBeGreaterThanOrEqual(15);
      expect(r.vertexThreshold).toBeLessThanOrEqual(100);
    }

    // At low zoom, pixelBased exceeds ceiling but capped at 100
    expect(result[0].pixelBased).toBeGreaterThan(100); // zoom -2: 10*16/0.25 = 640
    expect(result[0].vertexThreshold).toBe(100);

    // At zoom 0: pixelBased = 10 * 16 / 1 = 160, capped at 100
    const zoomZero = result.find(r => r.zoom === 0);
    expect(zoomZero!.pixelBased).toBe(160);
    expect(zoomZero!.vertexThreshold).toBe(100);
  });

  test('snap still catches targets at 200 EU threshold', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      // Simulate shapes 150 EU apart (within 200 threshold)
      const bounds = { minX: 100, maxX: 200, minY: 0, maxY: 100 };
      const candidate = { minX: 350, maxX: 500, minY: 0, maxY: 100 };
      // Distance: 350 - 200 = 150

      const snap150 = mod.computeSnapOffset(bounds, [candidate], null, 0, 200);
      // Distance: 201 (just over threshold)
      const candidate2 = { minX: 401, maxX: 500, minY: 0, maxY: 100 };
      const snap201 = mod.computeSnapOffset(bounds, [candidate2], null, 0, 200);

      return { snap150, snap201 };
    });

    // 150 EU apart: within threshold → snap fires
    expect(result.snap150.dx).toBe(150);
    // 201 EU apart: just over threshold → no snap
    expect(result.snap201.dx).toBe(0);
  });
});

// ─── snapAngleToDirection Tests ─────────────────────────────────────────────

test.describe('Map Editor Snap - Angle Snap', () => {
  test.beforeEach(async ({ adminUser }) => {
    await adminUser.goto('/admin/map');
    await adminUser.waitForLoadState('networkidle');
  });

  test('snaps to 16 directions (22.5° increments)', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');
      const step = Math.PI / 8; // 22.5°
      const results = [];

      // Test near each of the 16 directions
      for (let i = 0; i < 16; i++) {
        const targetAngle = i * step;
        // Test with small offset
        const offset = step * 0.1; // 10% of step
        const snapped = mod.snapAngleToDirection(targetAngle + offset);
        results.push({
          direction: i,
          snapped: Math.round(snapped * 1000) / 1000,
          expected: Math.round(targetAngle * 1000) / 1000,
        });
      }
      return results;
    });

    for (const r of result) {
      expect(r.snapped).toBe(r.expected);
    }
  });
});

// ─── Server Grid Lines Tests ────────────────────────────────────────────────

test.describe('Map Editor Snap - Server Grid Lines', () => {
  test.beforeEach(async ({ adminUser }) => {
    await adminUser.goto('/admin/map');
    await adminUser.waitForLoadState('networkidle');
  });

  test('generates correct grid lines for Calypso-sized planet', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      // Calypso: X=2, Y=3, Width=9, Height=9
      const planet = { Properties: { Map: { X: 2, Y: 3, Width: 9, Height: 9 } } };
      const grid = mod.getServerGridLines(planet);
      return {
        xCount: grid.xLines.length,
        yCount: grid.yLines.length,
        firstX: grid.xLines[0],
        lastX: grid.xLines[grid.xLines.length - 1],
        firstY: grid.yLines[0],
        lastY: grid.yLines[grid.yLines.length - 1],
      };
    });

    // Width=9 → 10 lines (0 to 9 inclusive)
    expect(result.xCount).toBe(10);
    expect(result.yCount).toBe(10);
    // First X = 2 * 8192 = 16384
    expect(result.firstX).toBe(16384);
    // Last X = (2 + 9) * 8192 = 90112
    expect(result.lastX).toBe(90112);
    // First Y = 3 * 8192 = 24576
    expect(result.firstY).toBe(24576);
    // Last Y = (3 + 9) * 8192 = 98304
    expect(result.lastY).toBe(98304);
  });
});

// ─── getGridSpacing Tests ────────────────────────────────────────────────────

test.describe('Map Editor Snap - Grid Spacing', () => {
  test.beforeEach(async ({ adminUser }) => {
    await adminUser.goto('/admin/map');
    await adminUser.waitForLoadState('networkidle');
  });

  test('returns power-of-2 spacing that keeps lines >= 50px apart', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');
      const ratio = 16; // typical: 8192 / 512
      const results = [];

      for (const zoom of [-2, -1, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10]) {
        const spacing = mod.getGridSpacing(zoom, ratio);
        const scale = Math.pow(2, zoom);
        const euPerPixel = ratio / scale;
        const pxPerLine = spacing / euPerPixel;
        results.push({ zoom, spacing, pxPerLine: Math.round(pxPerLine) });
      }
      return results;
    });

    for (const r of result) {
      // Spacing must be a power of 2
      expect(r.spacing).toBeGreaterThan(0);
      expect(Math.log2(r.spacing) % 1).toBe(0);
      // Lines must be at least 50px apart
      expect(r.pxPerLine).toBeGreaterThanOrEqual(50);
      // But not excessively far apart (should be < 100px to maximize detail)
      expect(r.pxPerLine).toBeLessThan(100);
      // Must not exceed SERVER_TILE_SIZE
      expect(r.spacing).toBeLessThanOrEqual(8192);
    }
  });

  test('returns 1 EU spacing at very high zoom', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');
      const ratio = 16;
      // At zoom 10: scale = 1024, euPerPixel = 16/1024 = 0.015625
      // minSpacing = 0.015625 * 50 = 0.78125 → spacing = 1
      return mod.getGridSpacing(10, ratio);
    });

    expect(result).toBe(1);
  });

  test('returns SERVER_TILE_SIZE at very low zoom', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');
      const ratio = 16;
      // At zoom -5: scale = 0.03125, euPerPixel = 16/0.03125 = 512
      // minSpacing = 512 * 50 = 25600 → spacing doubles past 8192 but clamped
      return mod.getGridSpacing(-5, ratio);
    });

    expect(result).toBe(8192);
  });

  test('spacing decreases as zoom increases', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');
      const ratio = 16;
      const spacings = [];

      for (let zoom = -2; zoom <= 10; zoom++) {
        spacings.push(mod.getGridSpacing(zoom, ratio));
      }
      return spacings;
    });

    // Each spacing should be <= the previous one (monotonically decreasing)
    for (let i = 1; i < result.length; i++) {
      expect(result[i]).toBeLessThanOrEqual(result[i - 1]);
    }
  });
});

// ─── Bisector Snap Tests ─────────────────────────────────────────────────────

test.describe('Map Editor Snap - Bisector Snap', () => {
  test.beforeEach(async ({ adminUser }) => {
    await adminUser.goto('/admin/map');
    await adminUser.waitForLoadState('networkidle');
  });

  test('snaps vertex to bisector of right-angle corner (45 degrees)', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      // Rectangle corner at (1000, 1000) with edges going right (+X) and up (+Y)
      // prev=(1000, 1200), next=(1200, 1000) → edges: left and down from corner
      // Interior bisector direction: normalize((0,200) + (200,0)) = normalize(200,200) = (0.707, 0.707)
      // Exterior bisector (going away from shape): (-0.707, -0.707) direction
      const cv = [
        { x: 1000, y: 1000, prevX: 1000, prevY: 1200, nextX: 1200, nextY: 1000 },
      ];

      // Vertex on the exterior bisector line (t < 0), offset by ~70.7 EU along (-1,-1) direction
      // Exact position on bisector: (950, 950)
      // Slightly off bisector: (952, 948) — perp distance ~2.83 EU
      const snap = mod.computeVertexSnap(952, 948, cv, null, 0, 50);

      // Should snap to the bisector line projection: (950, 950)
      return {
        dx: snap.dx,
        dy: snap.dy,
        finalX: 952 + snap.dx,
        finalY: 948 + snap.dy,
        bisector: snap.bisector,
      };
    });

    // The projected point on the bisector should be (950, 950)
    expect(result.finalX).toBeCloseTo(950, 0);
    expect(result.finalY).toBeCloseTo(950, 0);
    // Bisector info should be returned for guide visualization
    expect(result.bisector).not.toBeNull();
    expect(result.bisector.cx).toBe(1000);
    expect(result.bisector.cy).toBe(1000);
  });

  test('bisector direction is correct for non-right-angle corner', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      // Acute angle corner: edges at 0° and 60° from corner
      // Corner at (1000, 1000), prev at (1200, 1000) [+X], next at (1100, 1173) [~60°]
      const cv = [
        { x: 1000, y: 1000, prevX: 1200, prevY: 1000, nextX: 1100, nextY: 1173 },
      ];

      // Bisector should point roughly at 30° from horizontal (between 0° and 60°)
      // Interior bisector: normalize((1,0) + (0.5,0.866)) = normalize(1.5, 0.866)
      // = (0.866, 0.5) ≈ 30° direction
      // Exterior: (-0.866, -0.5)
      // Point on exterior bisector at t=-50: (1000 - 43.3, 1000 - 25) ≈ (957, 975)
      // Slightly off: (958, 973)
      const snap = mod.computeVertexSnap(958, 973, cv, null, 0, 50);

      return {
        dx: snap.dx,
        dy: snap.dy,
        bisector: snap.bisector,
      };
    });

    // Bisector should fire (non-null)
    expect(result.bisector).not.toBeNull();
    // The bisector direction should be approximately (0.866, 0.5) (30°)
    expect(result.bisector.dirX).toBeCloseTo(0.866, 1);
    expect(result.bisector.dirY).toBeCloseTo(0.5, 1);
  });

  test('axis snap wins over bisector when closer', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      // Right-angle corner at (1000, 1000)
      const cv = [
        { x: 1000, y: 1000, prevX: 1000, prevY: 1200, nextX: 1200, nextY: 1000 },
      ];

      // Vertex at (1001, 940): very close to X=1000 axis match (dx=-1)
      // Y=940 is 60 away from 1000, beyond threshold=50 → no Y snap
      // Axis snap total displacement = 1 EU
      // Bisector projection ≈ (970, 970), displacement ≈ 43 EU → axis wins
      const snap = mod.computeVertexSnap(1001, 940, cv, null, 0, 50);

      return {
        dx: snap.dx,
        dy: snap.dy,
        bisector: snap.bisector,
      };
    });

    // Axis snap should win — tiny X correction, no bisector override
    expect(result.dx).toBe(-1);
    expect(result.dy).toBe(0); // Y beyond threshold
    expect(result.bisector).toBeNull();
  });

  test('bisector skipped for nearly 180-degree angle (straight edge)', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      // Nearly straight edge: prev and next in almost opposite directions
      const cv = [
        { x: 1000, y: 1000, prevX: 800, prevY: 1001, nextX: 1200, nextY: 999 },
      ];

      // Vertex near the degenerate corner
      const snap = mod.computeVertexSnap(1005, 1005, cv, null, 0, 50);

      return {
        bisector: snap.bisector,
      };
    });

    // Bisector should be null (skipped due to nearly 180° angle)
    expect(result.bisector).toBeNull();
  });

  test('bisector snap returns correct guide info for visualization', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      // Right-angle corner at (2000, 3000)
      const cv = [
        { x: 2000, y: 3000, prevX: 2000, prevY: 3200, nextX: 2200, nextY: 3000 },
      ];

      // Vertex on the bisector, slightly off — should snap
      const snap = mod.computeVertexSnap(1952, 2948, cv, null, 0, 100);

      return snap.bisector;
    });

    expect(result).not.toBeNull();
    expect(result.cx).toBe(2000);
    expect(result.cy).toBe(3000);
    // For right-angle corner: bisector direction = normalize(1,1) ≈ (0.707, 0.707)
    expect(result.dirX).toBeCloseTo(0.707, 2);
    expect(result.dirY).toBeCloseTo(0.707, 2);
  });

  test('bisector snap works with gap-offset vertex snaps nearby', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      // Corner at (1000, 1000) with right angle
      const cv = [
        { x: 1000, y: 1000, prevX: 1000, prevY: 1200, nextX: 1200, nextY: 1000 },
      ];

      // Vertex at (953, 947): close to exterior bisector line through (1000,1000)
      // Bisector proj ≈ (950, 950), perp dist ~4.2 EU
      // No gap-offset match since gap=0 and exact coord match at 1000 is 47-53 EU away
      // Bisector displacement ≈ sqrt(3² + 3²) ≈ 4.2 EU
      // Axis snap: dx = 1000-953 = 47 (too far for close match)
      const snap = mod.computeVertexSnap(953, 947, cv, null, 0, 100);

      return {
        dx: snap.dx,
        dy: snap.dy,
        finalX: 953 + snap.dx,
        finalY: 947 + snap.dy,
        bisector: snap.bisector,
      };
    });

    // Bisector should win (small perpendicular correction vs large axis correction)
    expect(result.bisector).not.toBeNull();
    expect(result.finalX).toBeCloseTo(950, 0);
    expect(result.finalY).toBeCloseTo(950, 0);
  });

  test('bisector gap snap: snaps to gap distance from corner along bisector', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      // Right-angle corner at (1000, 1000), bisector direction ≈ (-0.707, -0.707)
      const cv = [
        { x: 1000, y: 1000, prevX: 1000, prevY: 1200, nextX: 1200, nextY: 1000 },
      ];

      const gap = 5;
      // Gap point on exterior bisector: (1000 - 5*0.707, 1000 - 5*0.707) ≈ (996.46, 996.46)
      // Place vertex near that gap point: (997, 996)
      const snap = mod.computeVertexSnap(997, 996, cv, null, gap, 50);
      const finalX = 997 + snap.dx;
      const finalY = 996 + snap.dy;
      const distToCorner = Math.sqrt((finalX - 1000) ** 2 + (finalY - 1000) ** 2);

      return {
        dx: snap.dx,
        dy: snap.dy,
        finalX,
        finalY,
        distToCorner: Math.round(distToCorner),
        bisector: snap.bisector,
      };
    });

    // Should snap to exactly gap=5 distance from corner along bisector
    expect(result.distToCorner).toBe(5);
    expect(result.bisector).not.toBeNull();
    expect(result.bisector.cx).toBe(1000);
    expect(result.bisector.cy).toBe(1000);
  });

  test('computeVertexSnap returns gap in result object', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      const snap1 = mod.computeVertexSnap(100, 100, [], null, 5, 50);
      const snap2 = mod.computeVertexSnap(100, 100, [], null, 0, 50);
      const snap3 = mod.computeVertexSnap(100, 100, [], null, 42, 50);

      return { gap1: snap1.gap, gap2: snap2.gap, gap3: snap3.gap };
    });

    expect(result.gap1).toBe(5);
    expect(result.gap2).toBe(0);
    expect(result.gap3).toBe(42);
  });

  test('per-axis distance equals zero for exact vertex match', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      // Vertex very close to candidate — snaps exactly on it
      const cv = [{ x: 1000, y: 2000 }];
      const snap = mod.computeVertexSnap(1003, 1997, cv, null, 0, 50);
      const snappedX = 1003 + snap.dx;
      const distX = Math.round(Math.abs(snappedX - snap.guideX));
      const snappedY = 1997 + snap.dy;
      const distY = Math.round(Math.abs(snappedY - snap.guideY));

      return { distX, distY, snappedX, snappedY };
    });

    // Exact match: snapped position equals guide position → distance = 0
    expect(result.distX).toBe(0);
    expect(result.distY).toBe(0);
    expect(result.snappedX).toBe(1000);
    expect(result.snappedY).toBe(2000);
  });

  test('per-axis distance equals gap for gap-offset snap', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      const cv = [{ x: 1000, y: 2000 }];
      const gap = 5;
      // Vertex approaching from right: should snap to x=1005 (cv.x + gap)
      const snap = mod.computeVertexSnap(1006, 1998, cv, null, gap, 50);
      const snappedX = 1006 + snap.dx;
      const snappedY = 1998 + snap.dy;
      const distX = Math.round(Math.abs(snappedX - snap.guideX));
      const distY = Math.round(Math.abs(snappedY - snap.guideY));

      return { distX, distY, snappedX, snappedY, guideX: snap.guideX, guideY: snap.guideY, gap: snap.gap };
    });

    // Gap-offset on X: snapped at gap distance from guide → distance = gap
    expect(result.distX).toBe(5);
    expect(result.snappedX).toBe(1005); // cv.x + gap
    expect(result.guideX).toBe(1000); // guide points at the candidate vertex
    // Exact match on Y: snapped directly to guideY → distance = 0
    expect(result.distY).toBe(0);
    expect(result.snappedY).toBe(2000);
    expect(result.gap).toBe(5);
  });
});
