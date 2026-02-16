// @ts-nocheck
import { getExchangeCategorizationSummaryJson } from '$lib/market/cache';

export async function GET({ fetch, request }) {
  try {
    const { json, etag, brotli, gzip } = await getExchangeCategorizationSummaryJson(fetch);

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

    // Serve pre-compressed buffers directly (compressed once at build time, not per-request)
    if (ae.includes('br') && brotli) {
      headers.set('Content-Encoding', 'br');
      return new Response(brotli, { status: 200, headers });
    }
    if (ae.includes('gzip') && gzip) {
      headers.set('Content-Encoding', 'gzip');
      return new Response(gzip, { status: 200, headers });
    }
    return new Response(json, { status: 200, headers });
  } catch (e) {
    return new Response(JSON.stringify({ error: 'Failed to retrieve market cache' }), {
      status: 500,
      headers: { 'Content-Type': 'application/json; charset=utf-8' }
    });
  }
}
