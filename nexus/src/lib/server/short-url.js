//@ts-nocheck

const DEFAULT_CANONICAL_PUBLIC_URL = 'https://entropianexus.com';
const DEFAULT_SHORT_REDIRECT_HOSTS = 'eunex.us,www.eunex.us';

/**
 * Manual short-code map.
 * Each key maps to a long-form prefix route on the canonical host.
 */
export const SHORT_ROUTE_MAP = Object.freeze({
  h: '/',
  a: '/account/setup',
  l: '/login',
  d: '/discord',
  b: '/banned',
  p: '/sitemap',
  x: '/sitemap.xml',
  r: '/legal/privacy',
  e: '/legal/terms',
  u: '/users',
  s: '/societies',
  i: '/items',
  iw: '/items/weapons',
  ia: '/items/armorsets',
  ir: '/items/armors',
  ij: '/items/attachments',
  ib: '/items/blueprints',
  ic: '/items/consumables',
  if: '/items/furnishings',
  il: '/items/clothing',
  im: '/items/materials',
  it: '/items/medicaltools',
  io: '/items/tools',
  ip: '/items/pets',
  iv: '/items/vehicles',
  ix: '/items/strongboxes',
  n: '/information',
  ng: '/information/guides',
  nm: '/information/mobs',
  ni: '/information/missions',
  np: '/information/professions',
  ns: '/information/skills',
  nv: '/information/vendors',
  nl: '/information/locations',
  ne: '/information/enumerations',
  m: '/maps',
  t: '/tools',
  tl: '/tools/loadouts',
  tc: '/tools/construction',
  k: '/market',
  ka: '/market/auction',
  ke: '/market/exchange',
  el: '/market/exchange/listings',
  eo: '/market/exchange/orders',
  ei: '/market/exchange/inventory',
  et: '/market/exchange/trades',
  kr: '/market/rental',
  ks: '/market/services',
  kh: '/market/shops',
  kz: '/market/shops-legacy'
});

/**
 * Pseudo-route transforms.
 * They map short patterns to long-form canonical routes.
 */
export const SHORT_PSEUDO_MAP = Object.freeze({
  mg: '/information/missions',
  mc: '/information/missions',
  eq: '/market/exchange'
});

function toBoolean(value, defaultValue = true) {
  if (value == null || value === '') return defaultValue;
  const v = String(value).trim().toLowerCase();
  return !(v === '0' || v === 'false' || v === 'off' || v === 'no');
}

export function normalizeHost(host) {
  if (!host) return '';
  return String(host)
    .trim()
    .toLowerCase()
    .replace(/\.$/, '')
    .replace(/:\d+$/, '');
}

function normalizePath(pathname) {
  if (!pathname || pathname === '') return '/';
  return pathname.startsWith('/') ? pathname : `/${pathname}`;
}

function parseHostList(csv) {
  return new Set(
    String(csv || '')
      .split(',')
      .map((x) => normalizeHost(x))
      .filter(Boolean)
  );
}

function getCanonicalOrigin(canonicalPublicUrl) {
  try {
    const parsed = new URL(canonicalPublicUrl || DEFAULT_CANONICAL_PUBLIC_URL);
    return `${parsed.protocol}//${parsed.host}`;
  } catch {
    return DEFAULT_CANONICAL_PUBLIC_URL;
  }
}

function joinPrefixAndTail(prefix, tailSegments) {
  const cleanPrefix = prefix === '/' ? '' : String(prefix || '').replace(/\/+$/, '');
  const cleanTail = (tailSegments || []).filter(Boolean).join('/');
  if (!cleanPrefix && !cleanTail) return '/';
  if (!cleanPrefix) return `/${cleanTail}`;
  if (!cleanTail) return cleanPrefix;
  return `${cleanPrefix}/${cleanTail}`;
}

export function isShortHost(host, env = process.env) {
  const configured = env?.SHORT_REDIRECT_HOSTS || DEFAULT_SHORT_REDIRECT_HOSTS;
  const hosts = parseHostList(configured);
  return hosts.has(normalizeHost(host));
}

function applyPseudoTransform(code, tailSegments, searchParams) {
  switch (code) {
    case 'mg': {
      const params = new URLSearchParams(searchParams);
      params.set('view', 'chains');
      return {
        path: SHORT_PSEUDO_MAP.mg,
        search: params.toString() ? `?${params.toString()}` : ''
      };
    }
    case 'mc': {
      const params = new URLSearchParams(searchParams);
      const chain = (tailSegments || []).join('/');
      params.set('view', 'chains');
      if (chain) params.set('chain', chain);
      return {
        path: SHORT_PSEUDO_MAP.mc,
        search: params.toString() ? `?${params.toString()}` : ''
      };
    }
    case 'eq': {
      const params = new URLSearchParams(searchParams);
      const itemId = (tailSegments || []).join('/');
      if (itemId) params.set('item', itemId);
      return {
        path: SHORT_PSEUDO_MAP.eq,
        search: params.toString() ? `?${params.toString()}` : ''
      };
    }
    default:
      return null;
  }
}

/**
 * Resolve short-host request into canonical long-form redirect.
 *
 * @param {object} input
 * @param {string} input.host - request host (may include port)
 * @param {string} input.path - pathname
 * @param {string} input.search - search string (includes ? or empty)
 * @param {object} [input.env] - environment values (defaults to process.env)
 * @returns {{ location: string, status: number } | null}
 */
export function resolveShortRedirect({ host, path, search = '', env = process.env }) {
  const enabled = toBoolean(env?.SHORT_REDIRECT_ENABLED, true);
  if (!enabled) return null;

  if (!isShortHost(host, env)) return null;

  const canonicalOrigin = getCanonicalOrigin(
    env?.CANONICAL_PUBLIC_URL || env?.VITE_URL || DEFAULT_CANONICAL_PUBLIC_URL
  );
  const canonicalHost = normalizeHost(new URL(canonicalOrigin).host);

  // Safety: avoid loops if canonical host is accidentally configured as a short host.
  if (isShortHost(canonicalHost, env)) return null;

  const pathname = normalizePath(path);
  const segments = pathname.split('/').filter(Boolean);
  const code = (segments[0] || '').toLowerCase();
  const tailSegments = segments.slice(1);

  if (SHORT_PSEUDO_MAP[code]) {
    const transformed = applyPseudoTransform(code, tailSegments, search);
    if (!transformed) return null;
    return {
      status: 301,
      location: `${canonicalOrigin}${transformed.path}${transformed.search}`
    };
  }

  const mappedPrefix = SHORT_ROUTE_MAP[code];
  if (mappedPrefix) {
    const targetPath = joinPrefixAndTail(mappedPrefix, tailSegments);
    return {
      status: 301,
      location: `${canonicalOrigin}${targetPath}${search || ''}`
    };
  }

  // Unknown code (or non-code path on short host): passthrough same path/query.
  return {
    status: 301,
    location: `${canonicalOrigin}${pathname}${search || ''}`
  };
}

