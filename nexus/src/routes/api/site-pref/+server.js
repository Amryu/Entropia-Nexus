// @ts-nocheck
import { pool } from '$lib/server/db.js';
import { getClientIp } from '$lib/server/route-analytics.js';

export async function POST(event) {
	let body;
	try {
		body = await event.request.json();
	} catch {
		return new Response(null, { status: 400 });
	}

	const ads = body.ads;
	if (ads !== 'granted' && ads !== 'denied') {
		return new Response(null, { status: 400 });
	}

	const ip = getClientIp(event);

	pool.query(
		`INSERT INTO consent_log (ip_address, ads_consent) VALUES ($1, $2)`,
		[ip || '0.0.0.0', ads]
	).catch(() => {});

	return new Response(null, { status: 204 });
}
