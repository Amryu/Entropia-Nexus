import { test, expect } from '../fixtures/auth';
import { TIMEOUT_SHORT, TIMEOUT_MEDIUM, TIMEOUT_LONG } from '../test-constants';

/**
 * Tests for the map editor snap functionality:
 * - Snap toolbar UI (Snap Edges, Snap Grid, Gap input)
 * - computeVertexSnap algorithm (vertex-to-vertex, gap-offset, grid lines, bisector)
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

// ─── getShapeEdges Tests ──────────────────────────────────────────────────

test.describe('Map Editor Snap - getShapeEdges', () => {
  test.beforeEach(async ({ adminUser }) => {
    await adminUser.goto('/admin/map');
    await adminUser.waitForLoadState('networkidle');
  });

  test('extracts polygon edges including closing edge', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');
      const loc = {
        Properties: {
          Shape: 'Polygon',
          Data: { vertices: [100, 200, 300, 200, 300, 400] },
        },
      };
      return mod.getShapeEdges(loc);
    });

    expect(result).toHaveLength(3);
    // Edge 0→1
    expect(result[0]).toEqual({ ax: 100, ay: 200, bx: 300, by: 200 });
    // Edge 1→2
    expect(result[1]).toEqual({ ax: 300, ay: 200, bx: 300, by: 400 });
    // Closing edge 2→0
    expect(result[2]).toEqual({ ax: 300, ay: 400, bx: 100, by: 200 });
  });

  test('extracts rectangle edges', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');
      const loc = {
        Properties: {
          Shape: 'Rectangle',
          Data: { x: 100, y: 200, width: 300, height: 150 },
        },
      };
      return mod.getShapeEdges(loc);
    });

    expect(result).toHaveLength(4);
    // Bottom edge
    expect(result[0]).toEqual({ ax: 100, ay: 200, bx: 400, by: 200 });
    // Right edge
    expect(result[1]).toEqual({ ax: 400, ay: 200, bx: 400, by: 350 });
    // Top edge
    expect(result[2]).toEqual({ ax: 400, ay: 350, bx: 100, by: 350 });
    // Left edge
    expect(result[3]).toEqual({ ax: 100, ay: 350, bx: 100, by: 200 });
  });

  test('returns empty for circles', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');
      return mod.getShapeEdges({
        Properties: { Shape: 'Circle', Data: { x: 100, y: 200, radius: 50 } },
      });
    });

    expect(result).toHaveLength(0);
  });

  test('returns empty for invalid shapes', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');
      return [
        mod.getShapeEdges(null),
        mod.getShapeEdges({}),
        mod.getShapeEdges({ Properties: { Shape: 'Polygon', Data: { vertices: [1, 2] } } }), // too few
      ];
    });

    for (const r of result) {
      expect(r).toHaveLength(0);
    }
  });
});

// ─── projectPointOnSegment Tests ─────────────────────────────────────────

test.describe('Map Editor Snap - projectPointOnSegment', () => {
  test.beforeEach(async ({ adminUser }) => {
    await adminUser.goto('/admin/map');
    await adminUser.waitForLoadState('networkidle');
  });

  test('projects onto middle of horizontal segment', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');
      // Horizontal edge from (100,200) to (400,200), point at (250, 220)
      return mod.projectPointOnSegment(250, 220, 100, 200, 400, 200);
    });

    expect(result.projX).toBe(250);
    expect(result.projY).toBe(200);
    expect(result.t).toBeCloseTo(0.5, 2);
    expect(result.distSq).toBe(400); // 20^2
  });

  test('clamps to segment start', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');
      // Point before segment start
      return mod.projectPointOnSegment(50, 200, 100, 200, 400, 200);
    });

    expect(result.projX).toBe(100);
    expect(result.projY).toBe(200);
    expect(result.t).toBe(0);
  });

  test('clamps to segment end', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');
      // Point past segment end
      return mod.projectPointOnSegment(500, 200, 100, 200, 400, 200);
    });

    expect(result.projX).toBe(400);
    expect(result.projY).toBe(200);
    expect(result.t).toBe(1);
  });

  test('projects onto diagonal segment', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');
      // 45° diagonal from (0,0) to (100,100), point at (50, 60)
      return mod.projectPointOnSegment(50, 60, 0, 0, 100, 100);
    });

    // Projection should be at (55, 55) — midpoint area on diagonal
    expect(result.projX).toBeCloseTo(55, 0);
    expect(result.projY).toBeCloseTo(55, 0);
    expect(result.t).toBeCloseTo(0.55, 2);
  });
});

// ─── Edge Snap Algorithm Tests ───────────────────────────────────────────

test.describe('Map Editor Snap - Edge Snap', () => {
  test.beforeEach(async ({ adminUser }) => {
    await adminUser.goto('/admin/map');
    await adminUser.waitForLoadState('networkidle');
  });

  test('vertex snaps to horizontal edge', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      const edges = [{ ax: 100, ay: 200, bx: 400, by: 200 }];
      // Point at (250, 210) — 10 units above the horizontal edge
      const snap = mod.computeVertexSnap(250, 210, [], null, 0, 50, edges);
      return {
        dx: snap.dx,
        dy: snap.dy,
        finalX: 250 + snap.dx,
        finalY: 210 + snap.dy,
        edge: snap.edge,
      };
    });

    // Should snap to (250, 200) on the edge
    expect(result.finalX).toBe(250);
    expect(result.finalY).toBe(200);
    expect(result.edge).not.toBeNull();
    expect(result.edge.isGap).toBe(false);
  });

  test('vertex snaps to vertical edge', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      const edges = [{ ax: 300, ay: 100, bx: 300, by: 400 }];
      // Point at (310, 250) — 10 units right of the vertical edge
      const snap = mod.computeVertexSnap(310, 250, [], null, 0, 50, edges);
      return {
        finalX: 310 + snap.dx,
        finalY: 250 + snap.dy,
        edge: snap.edge,
      };
    });

    // Should snap to (300, 250) on the edge
    expect(result.finalX).toBe(300);
    expect(result.finalY).toBe(250);
    expect(result.edge).not.toBeNull();
  });

  test('vertex snaps to diagonal edge', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      // 45° diagonal edge from (0,0) to (200,200)
      const edges = [{ ax: 0, ay: 0, bx: 200, by: 200 }];
      // Point at (100, 110) — slightly above the diagonal
      const snap = mod.computeVertexSnap(100, 110, [], null, 0, 50, edges);
      return {
        finalX: 100 + snap.dx,
        finalY: 110 + snap.dy,
        edge: snap.edge,
      };
    });

    // Should snap to (105, 105) on the diagonal
    expect(result.finalX).toBeCloseTo(105, 0);
    expect(result.finalY).toBeCloseTo(105, 0);
    expect(result.edge).not.toBeNull();
  });

  test('edge snap does not activate beyond threshold', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      const edges = [{ ax: 100, ay: 200, bx: 400, by: 200 }];
      // Point at (250, 300) — 100 units above the edge, threshold is 50
      const snap = mod.computeVertexSnap(250, 300, [], null, 0, 50, edges);
      return { dx: snap.dx, dy: snap.dy, edge: snap.edge };
    });

    expect(result.dx).toBe(0);
    expect(result.dy).toBe(0);
    expect(result.edge).toBeNull();
  });

  test('edge snap skips endpoints (t=0 and t=1)', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      const edges = [{ ax: 100, ay: 200, bx: 400, by: 200 }];
      // Point at (95, 205) — would project to t<0 (before segment start)
      const snap1 = mod.computeVertexSnap(95, 205, [], null, 0, 50, edges);
      // Point at (405, 195) — would project to t>1 (past segment end)
      const snap2 = mod.computeVertexSnap(405, 195, [], null, 0, 50, edges);
      return { snap1, snap2 };
    });

    // Should not trigger edge snap (endpoint projections)
    expect(result.snap1.edge).toBeNull();
    expect(result.snap2.edge).toBeNull();
  });

  test('vertex snap takes priority over edge snap when closer', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      // Vertex at (200, 200), edge from (100, 215) to (400, 215)
      const candidateVertices = [{ x: 200, y: 200 }];
      const edges = [{ ax: 100, ay: 215, bx: 400, by: 215 }];
      // Point at (202, 203): vertex snap = (200,200) → disp ~3.6, edge snap → (202,215) → disp 12
      const snap = mod.computeVertexSnap(202, 203, candidateVertices, null, 0, 50, edges);
      return {
        finalX: 202 + snap.dx,
        finalY: 203 + snap.dy,
        edge: snap.edge,
      };
    });

    // Vertex snap should win (closer)
    expect(result.finalX).toBe(200);
    expect(result.finalY).toBe(200);
    expect(result.edge).toBeNull();
  });

  test('edge snap wins when vertex snap is far', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      // Vertex at (200, 200) — far from point
      // Edge from (100, 305) to (400, 305) — point is 5 units from edge
      const candidateVertices = [{ x: 200, y: 200 }];
      const edges = [{ ax: 100, ay: 305, bx: 400, by: 305 }];
      // Point at (250, 300): vertex snap on X → dx=-50 (within threshold=100 but large),
      // vertex snap on Y → dy=-100 (at threshold limit),
      // edge snap → (250, 305) → disp 5
      const snap = mod.computeVertexSnap(250, 300, candidateVertices, null, 0, 100, edges);
      return {
        finalX: 250 + snap.dx,
        finalY: 300 + snap.dy,
        edge: snap.edge,
      };
    });

    // Edge snap should win (displacement 5 vs axis snap displacement ~50+)
    expect(result.finalX).toBeCloseTo(250, 0);
    expect(result.finalY).toBeCloseTo(305, 0);
    expect(result.edge).not.toBeNull();
  });

  test('edge gap-offset snap maintains gap distance from edge', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      // Horizontal edge at y=200
      const edges = [{ ax: 100, ay: 200, bx: 400, by: 200 }];
      const gap = 10;
      // Point at (250, 212) — should snap to (250, 210) which is gap=10 above the edge
      const snap = mod.computeVertexSnap(250, 212, [], null, gap, 50, edges);
      return {
        finalX: 250 + snap.dx,
        finalY: 212 + snap.dy,
        edge: snap.edge,
      };
    });

    // Should snap to gap distance above the edge
    expect(result.finalX).toBe(250);
    expect(result.finalY).toBe(210); // 200 + 10 gap
    expect(result.edge).not.toBeNull();
    expect(result.edge.isGap).toBe(true);
  });

  test('edge gap-offset snap from below', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      // Horizontal edge at y=200
      const edges = [{ ax: 100, ay: 200, bx: 400, by: 200 }];
      const gap = 10;
      // Point at (250, 188) — should snap to (250, 190) which is gap=10 below the edge
      const snap = mod.computeVertexSnap(250, 188, [], null, gap, 50, edges);
      return {
        finalX: 250 + snap.dx,
        finalY: 188 + snap.dy,
        edge: snap.edge,
      };
    });

    expect(result.finalX).toBe(250);
    expect(result.finalY).toBe(190); // 200 - 10 gap
    expect(result.edge).not.toBeNull();
    expect(result.edge.isGap).toBe(true);
  });

  test('edge snap returns correct edge info for visualization', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      const edges = [{ ax: 100, ay: 200, bx: 400, by: 200 }];
      const snap = mod.computeVertexSnap(250, 205, [], null, 0, 50, edges);
      return snap.edge;
    });

    expect(result).not.toBeNull();
    expect(result.ax).toBe(100);
    expect(result.ay).toBe(200);
    expect(result.bx).toBe(400);
    expect(result.by).toBe(200);
    expect(result.projX).toBe(250);
    expect(result.projY).toBe(200);
    expect(result.isGap).toBe(false);
  });

  test('no edge snap when candidateEdges is empty or omitted', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      // No edges parameter
      const snap1 = mod.computeVertexSnap(250, 205, [], null, 0, 50);
      // Empty edges array
      const snap2 = mod.computeVertexSnap(250, 205, [], null, 0, 50, []);
      return { edge1: snap1.edge, edge2: snap2.edge };
    });

    expect(result.edge1).toBeNull();
    expect(result.edge2).toBeNull();
  });
});
