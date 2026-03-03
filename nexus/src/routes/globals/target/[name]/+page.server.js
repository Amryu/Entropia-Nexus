// @ts-nocheck
import { decodeURIComponentSafe } from '$lib/util.js';

export async function load({ params, fetch }) {
  const targetName = decodeURIComponentSafe(params.name);

  try {
    const res = await fetch(`/api/globals/target/${encodeURIComponent(targetName)}`);
    if (!res.ok) {
      return { targetData: null, targetName };
    }
    const targetData = await res.json();
    return { targetData, targetName };
  } catch {
    return { targetData: null, targetName };
  }
}
