// @ts-nocheck
import { pageResponse } from '$lib/util';

export async function load() {
  // Entity data will be lazy loaded on client for faster initial page load
  return pageResponse(null, null, {});
}
