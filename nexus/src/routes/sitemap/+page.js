// @ts-nocheck
import { getAllLinks } from '$lib/sitemapUtil.js';

export async function load({ fetch }) {
  let links = await getAllLinks(fetch);

  return { links };
}