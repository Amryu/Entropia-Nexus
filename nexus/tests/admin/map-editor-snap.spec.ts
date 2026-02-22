import { test, expect } from '../fixtures/auth';
import { TIMEOUT_SHORT, TIMEOUT_MEDIUM, TIMEOUT_LONG } from '../test-constants';

/**
 * Tests for the map editor snap functionality:
 * - Snap toolbar UI (Snap, Snap Grid, Gap input)
 * - computeVertexSnap algorithm (edge extensions, grid lines, bisector, gap-offset)
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

    // Snap button
    const snapEdgesBtn = snapToolbar.getByRole('button', { name: 'Snap', exact: true });
    await expect(snapEdgesBtn).toBeVisible();

    // Snap Grid button
    const snapGridBtn = snapToolbar.getByRole('button', { name: 'Snap Grid' });
    await expect(snapGridBtn).toBeVisible();

    // Hint text
    const hint = snapToolbar.locator('.snap-hint');
    await expect(hint).toContainText('Shift+drag vertex');
  });

  test('gap input toggles with Snap button', async ({ adminUser }) => {
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

    // Snap enabled by default → gap input visible with value 5
    const snapEdgesBtn = snapToolbar.getByRole('button', { name: 'Snap', exact: true });
    const gapInput = snapToolbar.locator('.snap-gap-input');
    await expect(snapEdgesBtn).toHaveClass(/active/, { timeout: TIMEOUT_SHORT });
    await expect(gapInput).toBeVisible({ timeout: TIMEOUT_SHORT });
    await expect(gapInput).toHaveValue('20');

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

  test('snaps to grid lines (per-axis)', async ({ adminUser }) => {
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
    expect(result.snap1.guideX).toBe(16384);
    expect(result.snap1.guideY).toBe(24576);

    // Far: no snap
    expect(result.snap2.dx).toBe(0);
    expect(result.snap2.dy).toBe(0);

    // Near X grid only: dx = 24576 - 24570 = 6, dy = 0
    expect(result.snap3.dx).toBe(6);
    expect(result.snap3.dy).toBe(0);
    expect(result.snap3.guideX).toBe(24576);
    expect(result.snap3.guideY).toBeNull();
  });

  test('no snap when no candidates, grid, or edges', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');
      return mod.computeVertexSnap(500, 500, [], null, 0, 50);
    });

    expect(result.dx).toBe(0);
    expect(result.dy).toBe(0);
    expect(result.edge).toBeNull();
    expect(result.bisector).toBeNull();
    expect(result.guideX).toBeNull();
    expect(result.guideY).toBeNull();
  });

  test('returns gap value in result', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');
      const snap1 = mod.computeVertexSnap(100, 100, [], null, 20, 50);
      const snap2 = mod.computeVertexSnap(100, 100, [], null, 0, 50);
      const snap3 = mod.computeVertexSnap(100, 100, [], null, 42, 50);
      return { gap1: snap1.gap, gap2: snap2.gap, gap3: snap3.gap };
    });

    expect(result.gap1).toBe(20);
    expect(result.gap2).toBe(0);
    expect(result.gap3).toBe(42);
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

  test('strips duplicate closing vertex from polygon', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');
      // Closed ring: first vertex duplicated at end (common in DB data)
      const loc = {
        Properties: {
          Shape: 'Polygon',
          Data: { vertices: [100, 200, 300, 200, 300, 400, 100, 200] },
        },
      };
      return mod.getShapeVertices(loc);
    });

    // Should have 3 unique vertices, not 4
    expect(result).toHaveLength(3);
    // First vertex: prev should be LAST unique vertex (300,400), not itself
    expect(result[0].prevX).toBe(300);
    expect(result[0].prevY).toBe(400);
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

  test('edge snap wins over bisector when closer', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      // Right-angle corner at (1000, 1000) with two edges
      const cv = [
        { x: 1000, y: 1000, prevX: 1000, prevY: 1200, nextX: 1200, nextY: 1000 },
      ];
      // Horizontal edge at y=1000 from (1000,1000) to (1200,1000)
      const edges = [{ ax: 1000, ay: 1000, bx: 1200, by: 1000 }];

      // Vertex at (1100, 1002): 2 EU from the edge (very close), bisector projection much further
      const snap = mod.computeVertexSnap(1100, 1002, cv, null, 0, 50, edges);

      return {
        dx: snap.dx,
        dy: snap.dy,
        edge: snap.edge,
        bisector: snap.bisector,
      };
    });

    // Edge snap should win — tiny perpendicular correction
    expect(result.dy).toBe(-2);
    expect(result.edge).not.toBeNull();
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

  test('bisector competes with grid snap on displacement', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      // Right-angle corner at (1000, 1000)
      const cv = [
        { x: 1000, y: 1000, prevX: 1000, prevY: 1200, nextX: 1200, nextY: 1000 },
      ];
      // Grid lines far from vertex — grid snap displacement >> bisector displacement
      const gridLines = { xLines: [930], yLines: [930] };

      // Vertex at (952, 948): close to bisector (proj ≈ 950,950), disp ~4.2 EU
      // Grid snap: dx=-22, dy=-18, disp ~28 EU
      const snap = mod.computeVertexSnap(952, 948, cv, gridLines, 0, 100);

      return {
        bisector: snap.bisector,
        guideX: snap.guideX,
        guideY: snap.guideY,
      };
    });

    // Bisector should win (smaller displacement than grid)
    expect(result.bisector).not.toBeNull();
    // Grid guides should be cleared when bisector wins
    expect(result.guideX).toBeNull();
    expect(result.guideY).toBeNull();
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

  test('bounded edge snap does not extend beyond endpoints', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      const edges = [{ ax: 100, ay: 200, bx: 400, by: 200 }];
      // Point at (50, 205) — beyond segment start, no gap → no extension snap
      const snap1 = mod.computeVertexSnap(50, 205, [], null, 0, 50, edges);
      // Point at (450, 195) — beyond segment end, no gap → no extension snap
      const snap2 = mod.computeVertexSnap(450, 195, [], null, 0, 50, edges);
      return { snap1, snap2 };
    });

    // Without gap, no extension magnetic points → no edge snap beyond endpoints
    expect(result.snap1.edge).toBeNull();
    expect(result.snap2.edge).toBeNull();
  });

  test('edge snap skips near-exact endpoints (bisector handles corners)', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      const edges = [{ ax: 100, ay: 200, bx: 400, by: 200 }];
      // Point at (100, 205) — projects to t≈0 (very close to endpoint A)
      const snap1 = mod.computeVertexSnap(100, 205, [], null, 0, 50, edges);
      // Point at (400, 195) — projects to t≈1 (very close to endpoint B)
      const snap2 = mod.computeVertexSnap(400, 195, [], null, 0, 50, edges);
      return { snap1, snap2 };
    });

    // Near-exact endpoints should NOT trigger edge snap
    expect(result.snap1.edge).toBeNull();
    expect(result.snap2.edge).toBeNull();
  });

  test('edge snap wins over grid snap when closer', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      // Edge from (100, 305) to (400, 305) — point is 5 units from edge
      const gridLines = { xLines: [200], yLines: [250] };
      const edges = [{ ax: 100, ay: 305, bx: 400, by: 305 }];
      // Point at (250, 300): grid snap → dx=-50, dy=-50 (large displacement),
      // edge snap → (250, 305) → disp 5
      const snap = mod.computeVertexSnap(250, 300, [], gridLines, 0, 100, edges);
      return {
        finalX: 250 + snap.dx,
        finalY: 300 + snap.dy,
        edge: snap.edge,
        guideX: snap.guideX,
      };
    });

    // Edge snap should win (displacement 5 vs grid displacement ~70)
    expect(result.finalX).toBeCloseTo(250, 0);
    expect(result.finalY).toBeCloseTo(305, 0);
    expect(result.edge).not.toBeNull();
    // Grid guides cleared when edge wins
    expect(result.guideX).toBeNull();
  });

  test('grid snap wins over edge when closer', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      // Grid line very close to point, edge farther away
      const gridLines = { xLines: [251], yLines: [] };
      const edges = [{ ax: 100, ay: 350, bx: 400, by: 350 }];
      // Point at (250, 300): grid snap → dx=1, disp=1; edge snap → dy=50, disp=50
      const snap = mod.computeVertexSnap(250, 300, [], gridLines, 0, 100, edges);
      return {
        finalX: 250 + snap.dx,
        guideX: snap.guideX,
        edge: snap.edge,
      };
    });

    // Grid should win (displacement 1 vs edge 50)
    expect(result.finalX).toBe(251);
    expect(result.guideX).toBe(251);
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
    expect(result.isExtension).toBe(false);
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

  test('no gap-offset extension magnetic points (only direct line extensions)', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      // Horizontal edge at y=200 from x=100 to x=400
      const edges = [{ ax: 100, ay: 200, bx: 400, by: 200 }];
      const gap = 20;
      // Position where a gap-offset extension point WOULD be: (80, 220)
      // Should NOT snap — gap-offset extension magnetic points were removed
      // (82, 260) is far enough from direct extension point at (80,200) to avoid it
      const snap = mod.computeVertexSnap(82, 260, [], null, gap, 50, edges);
      return { edge: snap.edge };
    });

    // No extension snap — gap-offset extension magnetic points don't exist
    expect(result.edge).toBeNull();
  });

  test('extension magnetic point: direct line before endpoint A', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      // Horizontal edge from (100,200) to (400,200)
      const edges = [{ ax: 100, ay: 200, bx: 400, by: 200 }];
      const gap = 20;
      // Direct-line magnetic point before A: (100 - 20, 200) = (80, 200)
      // Place vertex near that: (82, 203)
      const snap = mod.computeVertexSnap(82, 203, [], null, gap, 50, edges);
      return {
        finalX: 82 + snap.dx,
        finalY: 203 + snap.dy,
        edge: snap.edge,
      };
    });

    // Should snap to (80, 200) — gap distance before endpoint A on direct line
    expect(result.finalX).toBe(80);
    expect(result.finalY).toBe(200);
    expect(result.edge).not.toBeNull();
    expect(result.edge.isGap).toBe(false);
    expect(result.edge.isExtension).toBe(true);
  });

  test('extension magnetic point: direct line after endpoint B', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      // Horizontal edge from (100,200) to (400,200)
      const edges = [{ ax: 100, ay: 200, bx: 400, by: 200 }];
      const gap = 20;
      // Direct-line magnetic point after B: (400 + 20, 200) = (420, 200)
      // Place vertex near that: (418, 197)
      const snap = mod.computeVertexSnap(418, 197, [], null, gap, 50, edges);
      return {
        finalX: 418 + snap.dx,
        finalY: 197 + snap.dy,
        edge: snap.edge,
      };
    });

    // Should snap to (420, 200) — gap distance after endpoint B on direct line
    expect(result.finalX).toBe(420);
    expect(result.finalY).toBe(200);
    expect(result.edge).not.toBeNull();
    expect(result.edge.isGap).toBe(false);
    expect(result.edge.isExtension).toBe(true);
  });

  test('edge extension not activated beyond threshold + gap distance', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      // Horizontal edge at y=200
      const edges = [{ ax: 100, ay: 200, bx: 400, by: 200 }];
      // Point at (50, 300) — 100 units away, threshold=50, gap=20 → 100 > 50+20
      const snap = mod.computeVertexSnap(50, 300, [], null, 20, 50, edges);
      return { edge: snap.edge };
    });

    expect(result.edge).toBeNull();
  });
});

// ─── projectPointOnLine Tests ──────────────────────────────────────────────

test.describe('Map Editor Snap - projectPointOnLine', () => {
  test.beforeEach(async ({ adminUser }) => {
    await adminUser.goto('/admin/map');
    await adminUser.waitForLoadState('networkidle');
  });

  test('projects onto infinite line with unclamped t', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');

      // Horizontal line from (100,200) to (400,200)
      // Point at (50, 210) — before segment start → t < 0
      const p1 = mod.projectPointOnLine(50, 210, 100, 200, 400, 200);
      // Point at (500, 190) — past segment end → t > 1
      const p2 = mod.projectPointOnLine(500, 190, 100, 200, 400, 200);
      // Point in middle — t between 0 and 1
      const p3 = mod.projectPointOnLine(250, 220, 100, 200, 400, 200);

      return { p1, p2, p3 };
    });

    // Before segment: t < 0, projects to (50, 200)
    expect(result.p1.t).toBeCloseTo(-1 / 6, 4);
    expect(result.p1.projX).toBeCloseTo(50, 0);
    expect(result.p1.projY).toBe(200);

    // Past segment: t > 1, projects to (500, 200)
    expect(result.p2.t).toBeCloseTo(4 / 3, 4);
    expect(result.p2.projX).toBeCloseTo(500, 0);
    expect(result.p2.projY).toBe(200);

    // In middle: t ≈ 0.5
    expect(result.p3.t).toBe(0.5);
    expect(result.p3.projX).toBe(250);
    expect(result.p3.projY).toBe(200);
    expect(result.p3.distSq).toBe(400); // 20^2
  });

  test('handles zero-length segment', async ({ adminUser }) => {
    const result = await adminUser.evaluate(async () => {
      const mod = await import('/src/lib/components/map-editor/mapEditorUtils.js');
      return mod.projectPointOnLine(50, 60, 100, 100, 100, 100);
    });

    // t = 0 for degenerate segment, projects to the point itself
    expect(result.t).toBe(0);
    expect(result.projX).toBe(100);
    expect(result.projY).toBe(100);
  });
});
