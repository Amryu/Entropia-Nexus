// @ts-nocheck
import sharp from 'sharp';
import { readFile, writeFile, mkdir, stat } from 'fs/promises';
import { existsSync } from 'fs';
import { resolve, dirname } from 'path';
import { apiCall } from '$lib/util.js';
import { getMobAreaDifficulty } from '$lib/mapUtil.js';

const OG_WIDTH = 1200;
const OG_HEIGHT = 1200;
const CACHE_MAX_AGE_SECONDS = 86400; // 1 day
const CACHE_REGEN_MS = 24 * 60 * 60 * 1000; // 24 hours

// In-memory cache: planetSlug -> { buffer, timestamp }
const memoryCache = new Map();

const COLOR_MAP = {
  Teleporter: 'aqua',
  MobArea: '#facc15',
  WaveEventArea: '#da70d6',
  PvpArea: 'orange',
  PvpLootArea: 'red',
  ZoneArea: 'blue',
  LandArea: 'green',
  CityArea: 'white',
  EstateArea: 'white',
  EventArea: 'white',
};

function getColor(loc) {
  if (loc.Properties?.AreaType === 'MobArea') {
    const diff = getMobAreaDifficulty(loc.Maturities);
    return diff?.color || '#facc15';
  }
  return COLOR_MAP[loc.Properties?.AreaType] || COLOR_MAP[loc.Properties?.Type] || 'white';
}

function isDefaultVisible(loc) {
  const type = loc.Properties?.Type;
  const areaType = loc.Properties?.AreaType;
  if (!type) return false;
  if (type === 'Teleporter') return true;
  if (areaType === 'MobArea' || areaType === 'WaveEventArea') return true;
  if (areaType === 'PvpArea' || areaType === 'PvpLootArea') return true;
  return false;
}

/**
 * Convert game coordinates to image pixel coordinates (matching MapCanvas formula).
 * Returns coordinates in the full-size source image space.
 */
function gameToImage(entropiaX, entropiaY, planet, imgWidth) {
  const imageTileSize = imgWidth / planet.Properties.Map.Width;
  const ratio = 8192 / imageTileSize;
  const ets = imageTileSize * ratio;
  const offsetX = planet.Properties.Map.X * ets;
  const offsetY = planet.Properties.Map.Y * ets;
  const height = planet.Properties.Map.Height * ets;
  return {
    x: (entropiaX - offsetX) / ratio,
    y: (height - (entropiaY - offsetY)) / ratio
  };
}

/**
 * Convert source image coords to OG output coords.
 * Accounts for fit: 'contain' scaling with padding to preserve aspect ratio.
 */
function imageToOg(imgX, imgY, srcW, srcH) {
  const scale = Math.min(OG_WIDTH / srcW, OG_HEIGHT / srcH);
  const padX = (OG_WIDTH - srcW * scale) / 2;
  const padY = (OG_HEIGHT - srcH * scale) / 2;
  return {
    x: imgX * scale + padX,
    y: imgY * scale + padY
  };
}

function gameToOg(eX, eY, planet, srcW, srcH) {
  const img = gameToImage(eX, eY, planet, srcW);
  return imageToOg(img.x, img.y, srcW, srcH);
}

function shapeToOg(data, planet, srcW, srcH) {
  if (!data) return null;
  if (data.centerX != null && data.radius != null) {
    const center = gameToOg(data.centerX, data.centerY, planet, srcW, srcH);
    const edge = gameToOg(data.centerX + data.radius, data.centerY, planet, srcW, srcH);
    return { type: 'circle', cx: center.x, cy: center.y, r: Math.abs(edge.x - center.x) };
  }
  if (data.originX != null && data.width != null) {
    const o = gameToOg(data.originX, data.originY, planet, srcW, srcH);
    const c = gameToOg(data.originX + data.width, data.originY + data.height, planet, srcW, srcH);
    return { type: 'rect', x: Math.min(o.x, c.x), y: Math.min(o.y, c.y), w: Math.abs(c.x - o.x), h: Math.abs(c.y - o.y) };
  }
  if (data.vertices && data.vertices.length >= 4) {
    const points = [];
    for (let i = 0; i < data.vertices.length; i += 2) {
      const p = gameToOg(data.vertices[i], data.vertices[i + 1], planet, srcW, srcH);
      points.push(`${p.x},${p.y}`);
    }
    return { type: 'polygon', points: points.join(' ') };
  }
  return null;
}

function esc(n) { return Number.isFinite(n) ? n.toFixed(1) : '0'; }

function buildSvgOverlay(locations, planet, srcW, srcH) {
  const elements = [];

  for (const loc of locations) {
    const color = getColor(loc);
    const shape = loc.Properties?.Shape;
    const data = loc.Properties?.Data;

    // Draw area shapes
    if (shape && data) {
      const geo = shapeToOg(data, planet, srcW, srcH);
      if (geo) {
        if (geo.type === 'circle') {
          elements.push(`<circle cx="${esc(geo.cx)}" cy="${esc(geo.cy)}" r="${esc(geo.r)}" fill="${color}" fill-opacity="0.25" stroke="${color}" stroke-opacity="0.6" stroke-width="1.5"/>`);
        } else if (geo.type === 'rect') {
          elements.push(`<rect x="${esc(geo.x)}" y="${esc(geo.y)}" width="${esc(geo.w)}" height="${esc(geo.h)}" fill="${color}" fill-opacity="0.25" stroke="${color}" stroke-opacity="0.6" stroke-width="1.5"/>`);
        } else if (geo.type === 'polygon') {
          elements.push(`<polygon points="${geo.points}" fill="${color}" fill-opacity="0.25" stroke="${color}" stroke-opacity="0.6" stroke-width="1.5"/>`);
        }
      }
    }

    // Draw point markers
    const coords = loc.Properties?.Coordinates;
    if (coords?.Longitude != null && coords?.Latitude != null) {
      const pt = gameToOg(coords.Longitude, coords.Latitude, planet, srcW, srcH);
      if (pt.x >= -20 && pt.x <= OG_WIDTH + 20 && pt.y >= -20 && pt.y <= OG_HEIGHT + 20) {
        if (loc.Properties?.Type === 'Teleporter') {
          elements.push(`<circle cx="${esc(pt.x)}" cy="${esc(pt.y)}" r="4" fill="aqua" fill-opacity="0.9" stroke="red" stroke-width="1.5"/>`);
        } else if (!shape) {
          elements.push(`<rect x="${esc(pt.x - 3)}" y="${esc(pt.y - 3)}" width="6" height="6" fill="${color}" fill-opacity="0.7" stroke="black" stroke-width="0.5"/>`);
        }
      }
    }
  }

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${OG_WIDTH}" height="${OG_HEIGHT}">${elements.join('')}</svg>`;
}

const STATIC_DIR = resolve(process.cwd(), 'static');

function getDiskCachePath(planetSlug) {
  return resolve(STATIC_DIR, 'og-cache', `map-${planetSlug}.jpg`);
}

async function isDiskCacheFresh(cachePath) {
  try {
    const stats = await stat(cachePath);
    return Date.now() - stats.mtimeMs < CACHE_REGEN_MS;
  } catch {
    return false;
  }
}

function getFromMemoryCache(planetSlug) {
  const entry = memoryCache.get(planetSlug);
  if (entry && Date.now() - entry.timestamp < CACHE_REGEN_MS) {
    return entry.buffer;
  }
  if (entry) memoryCache.delete(planetSlug);
  return null;
}

function setMemoryCache(planetSlug, buffer) {
  memoryCache.set(planetSlug, { buffer, timestamp: Date.now() });
}

export async function GET({ params, fetch }) {
  const planetSlug = params.planet?.replace(/[^a-zA-Z0-9]/g, '').toLowerCase();
  if (!planetSlug) {
    return new Response('Missing planet', { status: 400 });
  }

  const headers = {
    'Content-Type': 'image/jpeg',
    'Cache-Control': `public, max-age=${CACHE_MAX_AGE_SECONDS}`,
  };

  try {
    // Check in-memory cache first
    const memCached = getFromMemoryCache(planetSlug);
    if (memCached) {
      return new Response(memCached, { headers });
    }

    // Check disk cache
    const diskPath = getDiskCachePath(planetSlug);
    if (await isDiskCacheFresh(diskPath)) {
      const cached = await readFile(diskPath);
      setMemoryCache(planetSlug, cached);
      return new Response(cached, { headers });
    }

    // Load map image
    const mapImagePath = resolve(STATIC_DIR, `${planetSlug}.jpg`);
    if (!existsSync(mapImagePath)) {
      return new Response('Planet map not found', { status: 404 });
    }

    // Fetch planet and locations data
    const planets = await apiCall(fetch, '/planets');
    const planet = planets?.find(p => p.Name.replace(/[^a-zA-Z0-9]/g, '').toLowerCase() === planetSlug);
    if (!planet) {
      return new Response('Planet not found', { status: 404 });
    }

    let locations = [];
    try {
      locations = await apiCall(fetch, `/locations?Planet=${planet.Name}`) || [];
    } catch {
      // Proceed with no locations if API fails
    }

    const visible = locations.filter(isDefaultVisible);

    // Get source image dimensions
    const metadata = await sharp(mapImagePath).metadata();
    const srcW = metadata.width;
    const srcH = metadata.height;

    // Build SVG overlay at OG output dimensions
    const svg = buildSvgOverlay(visible, planet, srcW, srcH);
    const svgBuffer = Buffer.from(svg);

    // Resize preserving aspect ratio, pad with dark background, then overlay markers
    const imageBuffer = await sharp(mapImagePath)
      .resize(OG_WIDTH, OG_HEIGHT, {
        fit: 'contain',
        background: { r: 18, g: 18, b: 24, alpha: 1 }
      })
      .composite([{ input: svgBuffer, top: 0, left: 0 }])
      .jpeg({ quality: 80 })
      .toBuffer();

    // Cache to memory and disk
    setMemoryCache(planetSlug, imageBuffer);
    const cacheDir = dirname(diskPath);
    if (!existsSync(cacheDir)) {
      await mkdir(cacheDir, { recursive: true });
    }
    await writeFile(diskPath, imageBuffer).catch(() => {});

    return new Response(imageBuffer, { headers });
  } catch (err) {
    console.error('[og/map] Error generating preview:', err?.message || err);
    return new Response('Failed to generate preview', { status: 500, headers: { 'Cache-Control': 'no-cache' } });
  }
}
