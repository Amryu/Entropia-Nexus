// @ts-nocheck
import { requireVerified } from '$lib/server/auth.js';
import apiDocsRaw from '$lib/data/api-docs.md?raw';

export function GET({ locals }) {
	requireVerified(locals);
	return new Response(apiDocsRaw, {
		headers: {
			'Content-Type': 'text/markdown; charset=utf-8',
			'Content-Disposition': 'attachment; filename="entropia-nexus-api-docs.md"'
		}
	});
}
