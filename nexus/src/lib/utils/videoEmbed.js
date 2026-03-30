/**
 * Video embed utilities — URL parsing and embed generation for supported platforms.
 * Supports YouTube, Twitch Clips, and Vimeo.
 */

const YOUTUBE_ID_REGEX = /^[A-Za-z0-9_-]{11}$/;

/**
 * Platform definitions. Each has URL patterns, an ID extractor, and an embed URL builder.
 * @type {Array<{name: string, displayName: string, extractId: (url: URL) => string|null, getEmbedUrl: (id: string, parentHost?: string) => string}>}
 */
const PLATFORMS = [
  {
    name: 'youtube',
    displayName: 'YouTube',
    extractId(url) {
      const host = url.hostname.replace('www.', '');
      if (host === 'youtube.com' || host === 'youtube-nocookie.com') {
        const v = url.searchParams.get('v');
        if (v && YOUTUBE_ID_REGEX.test(v)) return v;
        const parts = url.pathname.split('/').filter(Boolean);
        if (['embed', 'shorts', 'live'].includes(parts[0]) && parts[1]) {
          const id = parts[1].split('?')[0];
          if (YOUTUBE_ID_REGEX.test(id)) return id;
        }
      } else if (host === 'youtu.be') {
        const id = url.pathname.slice(1).split('?')[0];
        if (YOUTUBE_ID_REGEX.test(id)) return id;
      }
      return null;
    },
    getEmbedUrl(id) {
      return `https://www.youtube-nocookie.com/embed/${id}`;
    },
  },
  {
    name: 'twitch-clip',
    displayName: 'Twitch Clip',
    extractId(url) {
      const host = url.hostname.replace('www.', '');
      if (host === 'clips.twitch.tv') {
        // clips.twitch.tv/{slug}
        const slug = url.pathname.split('/').filter(Boolean)[0];
        if (slug && /^[A-Za-z0-9_-]+$/.test(slug)) return slug;
      } else if (host === 'twitch.tv') {
        // twitch.tv/{channel}/clip/{slug}
        const parts = url.pathname.split('/').filter(Boolean);
        if (parts.length >= 3 && parts[1] === 'clip') {
          const slug = parts[2];
          if (/^[A-Za-z0-9_-]+$/.test(slug)) return slug;
        }
      }
      return null;
    },
    getEmbedUrl(id, parentHost) {
      const parent = parentHost || 'entropianexus.com';
      return `https://clips.twitch.tv/embed?clip=${id}&parent=${parent}`;
    },
  },
  {
    name: 'vimeo',
    displayName: 'Vimeo',
    extractId(url) {
      const host = url.hostname.replace('www.', '');
      if (host === 'vimeo.com') {
        // vimeo.com/{id} or vimeo.com/{id}/{hash}
        const id = url.pathname.split('/').filter(Boolean)[0];
        if (id && /^\d+$/.test(id)) return id;
      } else if (host === 'player.vimeo.com') {
        // player.vimeo.com/video/{id}
        const parts = url.pathname.split('/').filter(Boolean);
        if (parts[0] === 'video' && parts[1] && /^\d+$/.test(parts[1])) return parts[1];
      }
      return null;
    },
    getEmbedUrl(id) {
      return `https://player.vimeo.com/video/${id}`;
    },
  },
];

/**
 * Parse a video URL and return platform info, video ID, and embed URL.
 * @param {string} input - URL string
 * @param {string} [parentHost] - Hostname for Twitch embed parent parameter
 * @returns {{ platform: string, displayName: string, id: string, embedUrl: string, originalUrl: string } | null}
 */
export function parseVideoUrl(input, parentHost) {
  if (!input || typeof input !== 'string') return null;
  const trimmed = input.trim();
  if (!trimmed) return null;

  try {
    const url = new URL(trimmed);
    if (url.protocol !== 'http:' && url.protocol !== 'https:') return null;

    for (const platform of PLATFORMS) {
      const id = platform.extractId(url);
      if (id) {
        return {
          platform: platform.name,
          displayName: platform.displayName,
          id,
          embedUrl: platform.getEmbedUrl(id, parentHost),
          originalUrl: trimmed,
        };
      }
    }
  } catch {
    // Not a valid URL
  }

  return null;
}

/** List of supported platform display names for error messages. */
export const SUPPORTED_PLATFORM_NAMES = PLATFORMS.map(p => p.displayName);
