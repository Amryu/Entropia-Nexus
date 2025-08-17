//@ts-nocheck
import { v4 as uuidv4 } from 'uuid';

export async function GET({ request, cookies }) {
  let referer = request.headers.get('referer');

  if (!referer) {
    referer = import.meta.env.VITE_URL;
  }

  let refererUrl = new URL(referer);
  if (refererUrl.hostname !== import.meta.env.VITE_DOMAIN) {
    return new Response('Invalid referer! Someone may have tried to attack you.', {
      status: 400,
      body: 'Invalid referer! Someone may have tried to attack you.'
    });
  }

  let random = uuidv4();
  let state = `${random}-${referer}`;

  let redirectUri = process.env.DISCORD_REDIRECT_URI;

  let url = `https://discord.com/oauth2/authorize?client_id=1224999497130840105&response_type=code&redirect_uri=${encodeURIComponent(redirectUri)}&scope=identify&state=${state}`;

  console.log(import.meta.env.MODE);

  cookies.set(import.meta.env.VITE_STATE_COOKIE_NAME, random, {
    maxAge: 60 * 60 * 24 * 7,
    path: '/',
    secure: import.meta.env.MODE === 'development' ? false : true,
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