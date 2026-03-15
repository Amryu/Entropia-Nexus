import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const CACHE_DIR = join(__dirname, 'cache', 'maps');

const TYPE_COLORS = {
  MobArea: '#ffff00',
  LandArea: '#00ff00',
  PvpArea: '#ffa500',
  PvpLootArea: '#ff0000',
  ZoneArea: '#4169e1',
  CityArea: '#90ee90',
  EstateArea: '#deb887',
  EventArea: '#ffffff',
  WaveEventArea: '#da70d6',
  Area: '#cccccc'
};

const OLD_SHAPE_COLOR = '#888888';
const PADDING_FACTOR = 0.25;
const MIN_RENDER_SIZE = 300;
const MAX_RENDER_SIZE = 800;

/**
 * Render a map image showing the location shape for a change.
 * @param {object} changeData - The change's data (new state)
 * @param {object|null} oldEntity - The existing entity from the API (null for Create)
 * @param {object} planet - Planet object with Properties.Map
 * @returns {Buffer|null} PNG buffer, or null if rendering not possible
 */
export async function renderMapChange(changeData, oldEntity, planet) {
  const props = changeData?.Properties;
  if (!props?.Shape || !props?.Data) return null;
  if (!planet?.Properties?.Map) return null;

  let sharp, createCanvas, loadImage;
  try {
    sharp = (await import('sharp')).default;
    ({ createCanvas, loadImage } = await import('@napi-rs/canvas'));
  } catch {
    console.error('Map rendering unavailable: sharp or @napi-rs/canvas not installed');
    return null;
  }

  // Load planet map image (cached)
  const imageBuffer = await loadPlanetImage(planet.Name);
  if (!imageBuffer) return null;

  const metadata = await sharp(imageBuffer).metadata();
  const imgWidth = metadata.width;
  const imgHeight = metadata.height;

  // Build coordinate transforms
  const mapInfo = planet.Properties.Map;
  const imageTileSize = imgWidth / mapInfo.Width;
  const ratio = 8192 / imageTileSize;
  const offsetX = mapInfo.X * 8192;
  const offsetY = mapInfo.Y * 8192;
  const planetHeightE = mapInfo.Height * 8192;

  function toPixel(eX, eY) {
    const imgX = (eX - offsetX) / ratio;
    const imgY = (planetHeightE - (eY - offsetY)) / ratio;
    return { x: imgX, y: imgY };
  }

  function radiusToPixel(r) {
    return r / ratio;
  }

  // Compute bounding boxes for new and old shapes
  const newBounds = getShapeBounds(props.Shape, props.Data, toPixel, radiusToPixel);
  if (!newBounds) return null;

  const oldProps = oldEntity?.Properties;
  const hasOldShape = oldProps?.Shape && oldProps?.Data &&
    (oldProps.Shape !== props.Shape || JSON.stringify(oldProps.Data) !== JSON.stringify(props.Data));
  const oldBounds = hasOldShape ? getShapeBounds(oldProps.Shape, oldProps.Data, toPixel, radiusToPixel) : null;

  // Combined bounds with padding
  let minX = newBounds.minX, minY = newBounds.minY, maxX = newBounds.maxX, maxY = newBounds.maxY;
  if (oldBounds) {
    minX = Math.min(minX, oldBounds.minX);
    minY = Math.min(minY, oldBounds.minY);
    maxX = Math.max(maxX, oldBounds.maxX);
    maxY = Math.max(maxY, oldBounds.maxY);
  }

  const boundsW = maxX - minX;
  const boundsH = maxY - minY;
  const padX = Math.max(boundsW * PADDING_FACTOR, 30);
  const padY = Math.max(boundsH * PADDING_FACTOR, 30);

  // Crop region (clamped to image bounds)
  let cropX = Math.max(0, Math.floor(minX - padX));
  let cropY = Math.max(0, Math.floor(minY - padY));
  let cropW = Math.min(imgWidth - cropX, Math.ceil(boundsW + padX * 2));
  let cropH = Math.min(imgHeight - cropY, Math.ceil(boundsH + padY * 2));

  // Ensure minimum size
  if (cropW < MIN_RENDER_SIZE) {
    const diff = MIN_RENDER_SIZE - cropW;
    cropX = Math.max(0, cropX - diff / 2);
    cropW = Math.min(imgWidth - cropX, MIN_RENDER_SIZE);
  }
  if (cropH < MIN_RENDER_SIZE) {
    const diff = MIN_RENDER_SIZE - cropH;
    cropY = Math.max(0, cropY - diff / 2);
    cropH = Math.min(imgHeight - cropY, MIN_RENDER_SIZE);
  }

  cropX = Math.round(cropX);
  cropY = Math.round(cropY);
  cropW = Math.round(cropW);
  cropH = Math.round(cropH);

  // Scale down if too large
  let scale = 1;
  if (cropW > MAX_RENDER_SIZE || cropH > MAX_RENDER_SIZE) {
    scale = MAX_RENDER_SIZE / Math.max(cropW, cropH);
  }

  const canvasW = Math.round(cropW * scale);
  const canvasH = Math.round(cropH * scale);

  // Extract the crop region from the map image
  const croppedBuffer = await sharp(imageBuffer)
    .extract({ left: cropX, top: cropY, width: cropW, height: cropH })
    .resize(canvasW, canvasH)
    .toFormat('png')
    .toBuffer();

  // Draw shapes on canvas
  const canvas = createCanvas(canvasW, canvasH);
  const ctx = canvas.getContext('2d');

  // Draw map background
  const bgImage = await loadImage(croppedBuffer);
  ctx.drawImage(bgImage, 0, 0, canvasW, canvasH);

  // Transform for drawing: convert pixel coords to canvas coords
  function toCanvas(px, py) {
    return { x: (px - cropX) * scale, y: (py - cropY) * scale };
  }

  // Draw old shape (gray dashed) if shape changed
  if (hasOldShape) {
    drawShape(ctx, oldProps.Shape, oldProps.Data, toPixel, radiusToPixel, toCanvas, scale, {
      strokeColor: OLD_SHAPE_COLOR,
      fillColor: 'rgba(128, 128, 128, 0.2)',
      lineWidth: 2,
      dash: [8, 4]
    });
  }

  // Draw new shape
  const areaType = props.AreaType || 'Area';
  const color = TYPE_COLORS[areaType] || TYPE_COLORS.Area;
  drawShape(ctx, props.Shape, props.Data, toPixel, radiusToPixel, toCanvas, scale, {
    strokeColor: color,
    fillColor: hexToRgba(color, 0.3),
    lineWidth: 3,
    dash: null
  });

  return canvas.toBuffer('image/png');
}

function getShapeBounds(shape, data, toPixel, radiusToPixel) {
  if (shape === 'Circle' && data.x != null) {
    const center = toPixel(data.x, data.y);
    const rPx = radiusToPixel(data.radius);
    return { minX: center.x - rPx, minY: center.y - rPx, maxX: center.x + rPx, maxY: center.y + rPx };
  }
  if (shape === 'Rectangle' && data.x != null) {
    const tl = toPixel(data.x, data.y + data.height);
    const br = toPixel(data.x + data.width, data.y);
    return {
      minX: Math.min(tl.x, br.x), minY: Math.min(tl.y, br.y),
      maxX: Math.max(tl.x, br.x), maxY: Math.max(tl.y, br.y)
    };
  }
  if (shape === 'Polygon' && data.vertices?.length >= 6) {
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (let i = 0; i < data.vertices.length; i += 2) {
      const p = toPixel(data.vertices[i], data.vertices[i + 1]);
      minX = Math.min(minX, p.x); minY = Math.min(minY, p.y);
      maxX = Math.max(maxX, p.x); maxY = Math.max(maxY, p.y);
    }
    return { minX, minY, maxX, maxY };
  }
  return null;
}

function drawShape(ctx, shape, data, toPixel, radiusToPixel, toCanvas, scale, style) {
  ctx.strokeStyle = style.strokeColor;
  ctx.fillStyle = style.fillColor;
  ctx.lineWidth = style.lineWidth;
  if (style.dash) ctx.setLineDash(style.dash);
  else ctx.setLineDash([]);

  if (shape === 'Circle' && data.x != null) {
    const center = toCanvas(...Object.values(toPixel(data.x, data.y)));
    const rPx = radiusToPixel(data.radius) * scale;
    ctx.beginPath();
    ctx.arc(center.x, center.y, rPx, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  } else if (shape === 'Rectangle' && data.x != null) {
    const tl = toCanvas(...Object.values(toPixel(data.x, data.y + data.height)));
    const br = toCanvas(...Object.values(toPixel(data.x + data.width, data.y)));
    const x = Math.min(tl.x, br.x), y = Math.min(tl.y, br.y);
    const w = Math.abs(br.x - tl.x), h = Math.abs(br.y - tl.y);
    ctx.fillRect(x, y, w, h);
    ctx.strokeRect(x, y, w, h);
  } else if (shape === 'Polygon' && data.vertices?.length >= 6) {
    ctx.beginPath();
    for (let i = 0; i < data.vertices.length; i += 2) {
      const p = toCanvas(...Object.values(toPixel(data.vertices[i], data.vertices[i + 1])));
      if (i === 0) ctx.moveTo(p.x, p.y);
      else ctx.lineTo(p.x, p.y);
    }
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
  }

  ctx.setLineDash([]);
}

function hexToRgba(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

async function loadPlanetImage(planetName) {
  if (!existsSync(CACHE_DIR)) {
    await mkdir(CACHE_DIR, { recursive: true });
  }

  const slug = planetName.replace(/[^a-zA-Z0-9]/g, '').toLowerCase();
  const cachePath = join(CACHE_DIR, `${slug}.jpg`);

  // Return cached file if available
  if (existsSync(cachePath)) {
    return readFile(cachePath);
  }

  // Fetch from frontend
  const frontendUrl = process.env.FRONTEND_URL || 'https://entropianexus.com';
  const imageUrl = `${frontendUrl}/${slug}.jpg`;
  console.log(`Fetching planet map image: ${imageUrl}`);

  try {
    const response = await fetch(imageUrl);
    if (!response.ok) {
      console.error(`Failed to fetch map image ${imageUrl}: ${response.status}`);
      return null;
    }
    const buffer = Buffer.from(await response.arrayBuffer());
    await writeFile(cachePath, buffer);
    console.log(`Cached planet map image: ${cachePath}`);
    return buffer;
  } catch (e) {
    console.error(`Error fetching map image: ${e.message}`);
    return null;
  }
}
