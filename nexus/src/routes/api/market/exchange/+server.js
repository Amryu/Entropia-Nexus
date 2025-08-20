// @ts-nocheck
import { getExchangeCategorizationSummaryJson } from '$lib/market/cache';
import { brotliCompressSync, gzipSync } from 'node:zlib';

export async function GET({ fetch, request }) {
  try {
    const { json, etag } = await getExchangeCategorizationSummaryJson(fetch);
    const body = json;

    const ae = request.headers.get('accept-encoding') || '';
    const headers = new Headers({
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': 'public, max-age=60',
      'Vary': 'Accept-Encoding',
      ...(etag ? { 'ETag': etag } : {})
    });

    const inm = request.headers.get('if-none-match');
    if (etag && inm && inm === etag) {
      return new Response(null, { status: 304, headers });
    }

    if (ae.includes('br')) {
      headers.set('Content-Encoding', 'br');
      return new Response(brotliCompressSync(Buffer.from(body)), { status: 200, headers });
    }
    if (ae.includes('gzip')) {
      headers.set('Content-Encoding', 'gzip');
      return new Response(gzipSync(Buffer.from(body)), { status: 200, headers });
    }
    return new Response(body, { status: 200, headers });
  } catch (e) {
    return new Response(JSON.stringify({ error: 'Failed to retrieve market cache' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json; charset=utf-8' }
    });
  }
}
