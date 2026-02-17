// @ts-nocheck
import { apiCall } from '$lib/util.js';

export async function load({ fetch }) {
  const planets = await apiCall(fetch, '/planets');
  return { planets: planets || [] };
}
