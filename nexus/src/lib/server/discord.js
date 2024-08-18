//@ts-nocheck
const client_id = process.env.DISCORD_CLIENT_ID;
const client_secret = process.env.DISCORD_CLIENT_SECRET;
const redirect_uri = process.env.DISCORD_REDIRECT_URI;

export async function handleCode(code) {
  const data = new URLSearchParams();
  data.append('client_id', client_id);
  data.append('client_secret', client_secret);
  data.append('grant_type', 'authorization_code');
  data.append('code', code);
  data.append('redirect_uri', redirect_uri);

  const response = await fetch('https://discord.com/api/oauth2/token', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded'
    },
    body: new URLSearchParams({
      client_id: client_id,
      client_secret: client_secret,
      grant_type: 'authorization_code',
      code: code,
      redirect_uri: redirect_uri,
    })
  });

  return response.json();
}

export async function handleRefresh(token) {
  // Get Discord token
  let response = await fetch('https://discord.com/api/oauth2/token', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: new URLSearchParams({
      client_id: client_id,
      client_secret: client_secret,
      grant_type: 'refresh_token',
      refresh_token: token,
      redirect_uri: redirect_uri,
    }),
  });

  return response.json();
}

export async function handleRevoke(token) {
  let response = await fetch('https://discord.com/api/oauth2/token/revoke', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: new URLSearchParams({
      client_id: client_id,
      client_secret: client_secret,
      token: token,
    }),
  });

  return response.json();
}

export async function getUserInfo(token) {
  const response = await fetch('https://discord.com/api/users/@me', {
    headers: {
      Authorization: `Bearer ${token}`
    }
  });

  return response.json();
}