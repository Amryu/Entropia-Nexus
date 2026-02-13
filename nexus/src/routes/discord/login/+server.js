//@ts-nocheck
import { v4 as uuidv4 } from 'uuid';
import { isShortHost, normalizeHost } from '$lib/server/short-url.js';

export async function GET({ request, cookies, url: reqUrl }) {
  let referer = request.headers.get('referer');

  if (!referer) {
    referer = import.meta.env.VITE_URL;
  }

  let refererUrl = new URL(referer);
  const canonicalUrl = process.env.CANONICAL_PUBLIC_URL || import.meta.env.VITE_URL || 'https://entropianexus.com';
  let canonicalHost = normalizeHost(import.meta.env.VITE_DOMAIN);
  try {
    canonicalHost = normalizeHost(new URL(canonicalUrl).hostname);
  } catch {
    canonicalHost = normalizeHost(import.meta.env.VITE_DOMAIN);
  }
  const refererHost = normalizeHost(refererUrl.hostname);
  const mainHost = normalizeHost(import.meta.env.VITE_DOMAIN);
  const isAllowedMainHost = refererHost === mainHost || refererHost === canonicalHost;
  const isAllowedShortHost = isShortHost(refererHost);

  if (!isAllowedMainHost && !isAllowedShortHost) {
    return new Response('Invalid referer! Someone may have tried to attack you.', {
      status: 400
    });
  }

  // Defensive compatibility: if login was initiated from short host, normalize to canonical origin.
  if (isAllowedShortHost) {
    try {
      const canonicalOrigin = new URL(canonicalUrl).origin;
      referer = `${canonicalOrigin}${refererUrl.pathname}${refererUrl.search || ''}`;
    } catch {
      referer = `${import.meta.env.VITE_URL}${refererUrl.pathname}${refererUrl.search || ''}`;
    }
  }

  let random = uuidv4();
  let state = `${random}-${referer}`;

  let redirectUri = process.env.DISCORD_REDIRECT_URI;
  let clientId = process.env.DISCORD_CLIENT_ID;

  let url = `https://discord.com/oauth2/authorize?client_id=${clientId}&response_type=code&redirect_uri=${encodeURIComponent(redirectUri)}&scope=identify&state=${state}`;

  // Determine if we should use secure cookies based on protocol
  const isSecure = reqUrl.protocol === 'https:';

  cookies.set(import.meta.env.VITE_STATE_COOKIE_NAME, random, {
    maxAge: 60 * 60 * 24 * 7,
    path: '/',
    secure: isSecure,
    httpOnly: true,
    sameSite: 'Lax',
    domain: import.meta.env.VITE_DOMAIN
  });

  return new Response(null, {
    status: 302,
    headers: {
      location: url
    }
  });
}
