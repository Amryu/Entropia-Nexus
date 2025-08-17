const { Pool } = require('pg');
const credentials = require('../credentials');
const { recordQuery } = require('../metrics');

// Single shared pools for the whole API
const pool = new Pool(credentials.nexus);
const usersPool = new Pool(credentials['nexus-users']);

// Wrap query to record metrics and optionally log SQL at the endpoints layer
function wrapPool(p) {
	const origQuery = p.query.bind(p);
	const SQL_LOG = (process.env.SQL_LOG === '1' || process.env.SQL_LOG === 'true');
	const SQL_SLOW_MS = parseInt(process.env.SQL_SLOW_MS || '30', 10);

	p.query = async (...args) => {
		const start = process.hrtime.bigint();
		// Extract SQL text for logging
		let text = '';
		try {
			if (typeof args[0] === 'string') {
				text = args[0];
			} else if (args[0] && typeof args[0] === 'object' && args[0].text) {
				text = args[0].text;
			}
		} catch {}
		try {
			const res = await origQuery(...args);
			return res;
		} finally {
			const durMs = Number(process.hrtime.bigint() - start) / 1e6;
			try { recordQuery(durMs); } catch {}
			if (SQL_LOG || durMs >= SQL_SLOW_MS) {
				const preview = text ? text.replace(/\s+/g, ' ').slice(0, 600) : '[unknown-sql]';
				const paramsCount = Array.isArray(args[1]) ? args[1].length : (args[0] && Array.isArray(args[0].values) ? args[0].values.length : 0);
				console.log('[sql]', `${Math.round(durMs)}ms`, `(${paramsCount} params)`, preview);
			}
		}
	};
	return p;
}

wrapPool(pool);
wrapPool(usersPool);

module.exports = { pool, usersPool };
