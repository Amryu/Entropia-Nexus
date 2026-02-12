/**
 * Image enhancement utility for entity icons.
 * Provides auto-trim, upscaling, and contrast backdrop for better visibility.
 *
 * Used by the /api/img endpoint when ?mode=dark|light is specified.
 * Cloudflare CDN caches the result, so processing only happens once per unique URL.
 */
import sharp from 'sharp';

// Output canvas size (must match ICON_SIZE in imageProcessor.js)
const CANVAS_SIZE = 320;

// Padding around scaled content (percentage of canvas)
const PADDING_RATIO = 0.08;

// Maximum upscale factor to prevent pixelation
const MAX_SCALE_FACTOR = 3.0;

// Minimum trimmed content dimension — skip enhancement if content is smaller
const MIN_CONTENT_SIZE = 8;

// Extra pixels to preserve around trimmed content (protects anti-aliased edges)
const TRIM_MARGIN = 2;

// Mild sharpen applied after upscaling to recover detail
// sigma controls radius; flat/jagged control thresholds for flat vs textured areas
const SHARPEN_SIGMA = 0.8;
const SHARPEN_FLAT = 1.0;
const SHARPEN_JAGGED = 1.5;

// Brightness classification thresholds (0–255 luminance)
const BRIGHTNESS_DARK_THRESHOLD = 80;
const BRIGHTNESS_LIGHT_THRESHOLD = 180;

// Backdrop styling
const BACKDROP_RADIUS_RATIO = 0.42;
const BACKDROP_OPACITY_DARK = 0.07;   // Light backdrop on dark mode
const BACKDROP_OPACITY_LIGHT = 0.06;  // Dark backdrop on light mode

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
 * Main enhancement pipeline: trim transparent borders, scale up content,
 * and optionally add a contrast backdrop.
 *
 * @param {Buffer} imageBuffer - Original 320x320 WebP icon
 * @param {'dark'|'light'} mode - User's display theme
 * @returns {Promise<Buffer>} Enhanced WebP buffer
 */
export async function enhanceEntityImage(imageBuffer, mode) {
  const padding = Math.round(CANVAS_SIZE * PADDING_RATIO);
  const availableSize = CANVAS_SIZE - padding * 2;

  // Step 1: Trim transparent borders, then optionally re-extract with margin to preserve AA edges
  let trimmedBuffer, contentWidth = 0, contentHeight = 0;
  try {
    const trimResult = await sharp(imageBuffer)
      .ensureAlpha()
      .trim({ threshold: 10 })
      .toBuffer({ resolveWithObject: true });

    const { width: tw, height: th, trimOffsetLeft, trimOffsetTop } = trimResult.info;

    // Only attempt margin re-extraction if sharp provided valid offset info
    if (typeof trimOffsetLeft === 'number' && typeof trimOffsetTop === 'number'
        && tw > 0 && th > 0) {
      const origMeta = await sharp(imageBuffer).metadata();
      if (origMeta.width && origMeta.height) {
        const left = Math.max(0, trimOffsetLeft - TRIM_MARGIN);
        const top = Math.max(0, trimOffsetTop - TRIM_MARGIN);
        const right = Math.min(origMeta.width, trimOffsetLeft + tw + TRIM_MARGIN);
        const bottom = Math.min(origMeta.height, trimOffsetTop + th + TRIM_MARGIN);
        contentWidth = right - left;
        contentHeight = bottom - top;

        // Sanity check: extracted region must be valid and smaller than original
        if (contentWidth >= MIN_CONTENT_SIZE && contentHeight >= MIN_CONTENT_SIZE
            && contentWidth <= origMeta.width && contentHeight <= origMeta.height) {
          trimmedBuffer = await sharp(imageBuffer)
            .ensureAlpha()
            .extract({ left, top, width: contentWidth, height: contentHeight })
            .toBuffer();
        }
      }
    }

    // Fall back to sharp's own trim output if margin extraction was skipped or invalid
    if (!trimmedBuffer) {
      trimmedBuffer = trimResult.data;
      contentWidth = tw;
      contentHeight = th;
    }
  } catch {
    // Trim can fail on fully uniform images — return original
    return imageBuffer;
  }

  if (contentWidth < MIN_CONTENT_SIZE || contentHeight < MIN_CONTENT_SIZE) {
    return imageBuffer;
  }

  // Step 2: Calculate scale factor
  const maxDim = Math.max(contentWidth, contentHeight);
  const scaleFactor = Math.min(MAX_SCALE_FACTOR, availableSize / maxDim);

  const newWidth = Math.round(contentWidth * scaleFactor);
  const newHeight = Math.round(contentHeight * scaleFactor);

  // Step 3: Scale the trimmed content with mild sharpening when upscaling
  let scaledContent;
  try {
    let scaleOp = sharp(trimmedBuffer)
      .resize(newWidth, newHeight, { kernel: sharp.kernel.lanczos3, fit: 'fill' });

    if (scaleFactor > 1.05) {
      scaleOp = scaleOp.sharpen(SHARPEN_SIGMA, SHARPEN_FLAT, SHARPEN_JAGGED);
    }

    scaledContent = await scaleOp.toBuffer();
  } catch {
    // If sharpening fails, retry without it
    scaledContent = await sharp(trimmedBuffer)
      .resize(newWidth, newHeight, { kernel: sharp.kernel.lanczos3, fit: 'fill' })
      .toBuffer();
  }

  // Step 4: Brightness analysis and backdrop decision
  const brightness = await analyzeBrightness(trimmedBuffer);
  const backdropType = getBackdropType(mode, brightness);

  // Step 5: Composite onto transparent canvas
  const layers = [];

  if (backdropType) {
    layers.push({
      input: createBackdropSvg(backdropType, CANVAS_SIZE),
      top: 0,
      left: 0
    });
  }

  layers.push({
    input: scaledContent,
    top: Math.round((CANVAS_SIZE - newHeight) / 2),
    left: Math.round((CANVAS_SIZE - newWidth) / 2)
  });

  return sharp({
    create: {
      width: CANVAS_SIZE,
      height: CANVAS_SIZE,
      channels: 4,
      background: { r: 0, g: 0, b: 0, alpha: 0 }
    }
  })
    .composite(layers)
    .webp({ quality: 90 })
    .toBuffer();
}
