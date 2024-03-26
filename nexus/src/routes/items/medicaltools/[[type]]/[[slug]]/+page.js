// @ts-nocheck
let items;

import { handlePageLoad } from '$lib/util';

export async function load({ fetch, params }) {
  const config = {
    items: ['medicaltools', 'medicalchips'],
    types: [
      { type: 'tools', tierable: true },
      { type: 'chips', tierable: false }
    ]
  }

  let response;

  ({ items, response } = await handlePageLoad(fetch, items, config, params.slug, params.type));

  return response;
}