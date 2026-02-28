// @ts-nocheck

export async function load({ params, fetch }) {
  const playerName = decodeURIComponent(params.name);

  try {
    const res = await fetch(`/api/globals/player/${encodeURIComponent(playerName)}`);
    if (!res.ok) {
      return { playerData: null, playerName };
    }
    const playerData = await res.json();
    return { playerData, playerName };
  } catch {
    return { playerData: null, playerName };
  }
}
