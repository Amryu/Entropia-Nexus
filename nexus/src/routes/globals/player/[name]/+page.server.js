// @ts-nocheck
import { decodeURIComponentSafe } from '$lib/util.js';

export async function load({ params, fetch }) {
  const playerName = decodeURIComponentSafe(params.name);

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
