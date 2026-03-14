/**
 * Image variant generation for pre-generating resized versions.
 * Used during image approval to create all size variants upfront,
 * and by the migration script to backfill existing images.
 */
import sharp from 'sharp';

/** Standard resize sizes matching the /api/img/ endpoint */
export const VALID_SIZES = [32, 48, 64, 128];

/**
 * Generate all standard size variants from an icon and/or thumbnail buffer.
 * Prefers thumb as resize source (smaller file, faster processing).
 * Falls back to icon if thumb is not available.
 *
 * @param {Buffer} iconBuffer - The 320x320 icon image
 * @param {Buffer|null} thumbBuffer - The 128x128 thumbnail (optional)
 * @returns {Promise<Record<string, Buffer>>} Map of "s{size}" → WebP buffer
 */
export async function generateSizeVariants(iconBuffer, thumbBuffer) {
  const source = thumbBuffer || iconBuffer;
  /** @type {Record<string, Buffer>} */
  const variants = {};

  await Promise.all(VALID_SIZES.map(async (size) => {
    const quality = size <= 48 ? 80 : 85;
    const buffer = await sharp(source)
      .resize(size, size, { fit: 'cover', position: 'center' })
      .webp({ quality })
      .toBuffer();
    variants[`s${size}`] = buffer;
  }));

  return variants;
}
