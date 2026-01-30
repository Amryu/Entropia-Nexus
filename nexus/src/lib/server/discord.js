//@ts-nocheck

// Read environment variables at request time, not module load time
function getConfig() {
  return {
    client_id: process.env.DISCORD_CLIENT_ID,
    client_secret: process.env.DISCORD_CLIENT_SECRET,
    redirect_uri: process.env.DISCORD_REDIRECT_URI
  };
}

export async function handleCode(code) {
  const { client_id, client_secret, redirect_uri } = getConfig();

  // Log for debugging
  console.log('Discord OAuth - redirect_uri:', redirect_uri);
  console.log('Discord OAuth - client_id exists:', !!client_id);
  console.log('Discord OAuth - client_secret exists:', !!client_secret);

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
  const { client_id, client_secret, redirect_uri } = getConfig();

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
  const { client_id, client_secret } = getConfig();

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
