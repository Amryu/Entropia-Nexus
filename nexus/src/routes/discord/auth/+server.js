//@ts-nocheck
import { createSession, deleteSession, upsertUser, getUserFromSession } from '$lib/server/db.js';
import { getUserInfo, handleCode } from '$lib/server/discord.js';
import { v4 as uuidv4 } from 'uuid';

export async function GET({ cookies, url, locals }) {
  const state = url.searchParams.get('state').substring(0, 36);

  if (state !== cookies.get(import.meta.env.VITE_STATE_COOKIE_NAME)) {
    return new Response(null, {
      status: 400,
      body: 'Invalid state'
    });
  }

  let response = await handleCode(url.searchParams.get('code'));

  if (response.error) {
    return new Response(null, {
      status: 400,
      body: response.error
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
    secure: import.meta.env.MODE === 'development' ? false : true,
    httpOnly: true,
    sameSite: 'Lax',
    domain: import.meta.env.VITE_DOMAIN
  })

  cookies.set(import.meta.env.VITE_STATE_COOKIE_NAME, '', {
    maxAge: 0,
    path: '/',
    secure: import.meta.env.MODE === 'development' ? false : true,
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

  const redirect = url.searchParams.get('state').substring(37);

  return new Response(null, {
    status: 302,
    headers: {
      location: redirect
    }
  });
}