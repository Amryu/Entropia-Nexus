// @ts-nocheck
import { pool } from '$lib/server/db.js';
import { getClientIp } from '$lib/server/route-analytics.js';

const VALID_VALUES = ['granted', 'denied'];

export async function POST(event) {
	let body;
	try {
		body = await event.request.json();
	} catch {
		return new Response(null, { status: 400 });
	}

	const { analytics } = body;
	if (!VALID_VALUES.includes(analytics)) {
		return new Response(null, { status: 400 });
	}

	const ip = getClientIp(event);

	pool.query(
		`INSERT INTO consent_log (ip_address, ads_consent, analytics_consent) VALUES ($1, $2, $3)`,
		[ip || '0.0.0.0', 'denied', analytics]
	).catch(() => {});

	return new Response(null, { status: 204 });
}
