//@ts-nocheck
import { createSession, deleteSession, upsertUser, getUserFromSession } from '$lib/server/db.js';
import { getUserInfo, handleCode } from '$lib/server/discord.js';
import { v4 as uuidv4 } from 'uuid';

export async function GET({ cookies, url, locals }) {
  // Determine if we should use secure cookies based on protocol
  const isSecure = url.protocol === 'https:';
  const stateParam = url.searchParams.get('state');
  const code = url.searchParams.get('code');

  if (!stateParam) {
    return new Response('Missing state parameter', { status: 400 });
  }

  if (!code) {
    return new Response('Missing code parameter', { status: 400 });
  }

  const state = stateParam.substring(0, 36);
  const stateCookie = cookies.get(import.meta.env.VITE_STATE_COOKIE_NAME);

  if (!stateCookie || state !== stateCookie) {
    console.error('State mismatch - state:', state, 'cookie:', stateCookie, 'cookie exists:', !!stateCookie);
    return new Response('Invalid state - please try logging in again. This may happen if cookies are blocked or expired.', { status: 400 });
  }

  let response = await handleCode(code);

  if (response.error) {
    console.error('Discord OAuth error:', response.error, response.error_description);
    return new Response(`Discord OAuth error: ${response.error_description || response.error}`, {
      status: 400
    });
  }

  const accessToken = response.access_token;
  const refreshToken = response.refresh_token;
  const expires = Math.floor(Date.now() / 1000) + response.expires_in;

  let user = await getUserInfo(accessToken);

  await upsertUser(user);
  
  // Delete previous session if it exists
  let session = locals.session;
  if (session?.id) {
    await deleteSession(session.id);
  }
  let newSessionId = uuidv4();

  await createSession(user.id, newSessionId, accessToken, refreshToken, expires);

  cookies.set(import.meta.env.VITE_SESSION_COOKIE_NAME, newSessionId, {
    maxAge: 60 * 60 * 24 * 7,
    path: '/',
    secure: isSecure,
    httpOnly: true,
    sameSite: 'Lax',
    domain: import.meta.env.VITE_DOMAIN
  })

  cookies.set(import.meta.env.VITE_STATE_COOKIE_NAME, '', {
    maxAge: 0,
    path: '/',
    secure: isSecure,
    httpOnly: true,
    sameSite: 'Lax',
    domain: import.meta.env.VITE_DOMAIN
  });

  let dbUser = await getUserFromSession(newSessionId);

  if (dbUser?.verified !== true) {
    return new Response(null, {
      status: 302,
      headers: {
        location: '/account/setup'
      }
    });
  }

  const redirect = stateParam.substring(37) || '/';

  return new Response(null, {
    status: 302,
    headers: {
      location: redirect
    }
  });
}