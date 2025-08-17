// @ts-nocheck
import { getExchangeCategorizationSummary } from '$lib/market/cache';
import { brotliCompressSync, gzipSync } from 'node:zlib';

export async function GET({ fetch, request }) {
  try {
    const data = await getExchangeCategorizationSummary(fetch);
    const body = JSON.stringify(data);

    const ae = request.headers.get('accept-encoding') || '';
    const headers = new Headers({
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': 'public, max-age=60',
      'Vary': 'Accept-Encoding'
    });

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
