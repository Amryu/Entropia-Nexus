/**
 * Image enhancement utility for entity icons.
 * Adds an on-demand contrast backdrop for better visibility in dark/light themes.
 *
 * Used by the /api/img endpoint when ?mode=dark|light is specified.
 * Cloudflare CDN caches the result, so processing only happens once per unique URL.
 */
import sharp from 'sharp';

// Brightness classification thresholds (0–255 luminance)
const BRIGHTNESS_DARK_THRESHOLD = 80;
const BRIGHTNESS_LIGHT_THRESHOLD = 180;

// Backdrop styling
const BACKDROP_RADIUS_RATIO = 0.42;
const BACKDROP_OPACITY_DARK = 0.07;   // Light backdrop on dark mode
const BACKDROP_OPACITY_LIGHT = 0.06;  // Dark backdrop on light mode

// Transparency detection
const TRANSPARENCY_SAMPLE_SIZE = 64;
const TRANSPARENCY_PIXEL_THRESHOLD = 0.01; // 1% of sampled pixels must be transparent

/**
 * Detect whether an image has meaningful transparency (e.g. a transparent background).
 * Downsamples to 64x64 for performance, then checks if more than 1% of pixels
 * have alpha below 250.
 *
 * @param {Buffer} imageBuffer
 * @returns {Promise<boolean>}
 */
export async function hasTransparency(imageBuffer) {
  const metadata = await sharp(imageBuffer).metadata();
  if (!metadata.hasAlpha) return false;

  const { data } = await sharp(imageBuffer)
    .resize(TRANSPARENCY_SAMPLE_SIZE, TRANSPARENCY_SAMPLE_SIZE, { fit: 'inside' })
    .ensureAlpha()
    .raw()
    .toBuffer({ resolveWithObject: true });

  let transparentPixels = 0;
  const totalPixels = data.length / 4;
  for (let i = 3; i < data.length; i += 4) {
    if (data[i] < 250) transparentPixels++;
  }

  return transparentPixels > totalPixels * TRANSPARENCY_PIXEL_THRESHOLD;
}

/**
 * Analyze the average brightness of non-transparent pixels.
 * Downsamples to 32x32 for performance.
 *
 * @param {Buffer} imageBuffer
 * @returns {Promise<'dark'|'medium'|'light'>}
 */
async function analyzeBrightness(imageBuffer) {
  const SAMPLE_SIZE = 32;
  const { data } = await sharp(imageBuffer)
    .resize(SAMPLE_SIZE, SAMPLE_SIZE, { fit: 'inside' })
    .ensureAlpha()
    .raw()
    .toBuffer({ resolveWithObject: true });

  let totalLuminance = 0;
  let opaqueCount = 0;

  for (let i = 0; i < data.length; i += 4) {
    const a = data[i + 3];
    if (a > 127) {
      // Rec. 709 perceived luminance
      totalLuminance += 0.2126 * data[i] + 0.7152 * data[i + 1] + 0.0722 * data[i + 2];
      opaqueCount++;
    }
  }

  if (opaqueCount === 0) return 'medium';

  const avg = totalLuminance / opaqueCount;
  if (avg < BRIGHTNESS_DARK_THRESHOLD) return 'dark';
  if (avg > BRIGHTNESS_LIGHT_THRESHOLD) return 'light';
  return 'medium';
}

/**
 * Determine what backdrop type is needed (if any).
 *
 * @param {'dark'|'light'} mode - User's theme
 * @param {'dark'|'medium'|'light'} brightness - Image brightness
 * @returns {'light'|'dark'|null}
 */
function getBackdropType(mode, brightness) {
  if (mode === 'dark' && brightness === 'dark') return 'light';
  if (mode === 'light' && brightness === 'light') return 'dark';
  return null;
}

/**
 * Create a radial gradient backdrop as SVG buffer.
 *
 * @param {'light'|'dark'} type
 * @param {number} size - Canvas size
 * @returns {Buffer}
 */
function createBackdropSvg(type, size) {
  const r = Math.round(size * BACKDROP_RADIUS_RATIO);
  const cx = size / 2;
  const cy = size / 2;

  const color = type === 'light' ? '255,255,255' : '0,0,0';
  const opacity = type === 'light' ? BACKDROP_OPACITY_DARK : BACKDROP_OPACITY_LIGHT;

  return Buffer.from(
    `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}">
      <defs>
        <radialGradient id="bg" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stop-color="rgba(${color},${opacity})" />
          <stop offset="70%" stop-color="rgba(${color},${opacity * 0.6})" />
          <stop offset="100%" stop-color="rgba(${color},0)" />
        </radialGradient>
      </defs>
      <ellipse cx="${cx}" cy="${cy}" rx="${r}" ry="${r}" fill="url(#bg)" />
    </svg>`
  );
}

/**
 * On-demand backdrop enhancement for entity icons.
 * Adds a subtle radial gradient behind transparent images for contrast
 * against the user's theme. Non-transparent images are returned as-is.
 *
 * @param {Buffer} imageBuffer - WebP icon buffer
 * @param {'dark'|'light'} mode - User's display theme
 * @param {boolean} [transparent] - Cached transparency flag (skips pixel analysis if provided)
 * @returns {Promise<Buffer>} Enhanced WebP buffer
 */
export async function enhanceEntityImage(imageBuffer, mode, transparent) {
  // Use cached value or compute on-the-fly (fallback for legacy images)
  const isTransparent = transparent ?? await hasTransparency(imageBuffer);
  if (!isTransparent) {
    return imageBuffer;
  }

  // Determine if a contrast backdrop is needed based on image brightness vs theme
  const brightness = await analyzeBrightness(imageBuffer);
  const backdropType = getBackdropType(mode, brightness);

  if (!backdropType) return imageBuffer;

  // Composite backdrop behind the original image
  const meta = await sharp(imageBuffer).metadata();
  const width = meta.width || 320;
  const height = meta.height || 320;

  return sharp({
    create: {
      width,
      height,
      channels: 4,
      background: { r: 0, g: 0, b: 0, alpha: 0 }
    }
  })
    .composite([
      { input: createBackdropSvg(backdropType, Math.max(width, height)), top: 0, left: 0 },
      { input: imageBuffer, top: 0, left: 0 }
    ])
    .webp({ quality: 90 })
    .toBuffer();
}
