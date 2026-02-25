const { Pool, types } = require('pg');
const credentials = require('../credentials');
const { recordQuery } = require('../metrics');

// Parse common numeric types as JS numbers once to avoid per-field Number() costs
try {
	// numeric
	types.setTypeParser(1700, v => (v === null ? null : parseFloat(v)));
	// int8 — parse as number when safe, keep as string for large values (e.g. Discord snowflakes)
	types.setTypeParser(20, v => {
		if (v === null) return null;
		const n = parseInt(v, 10);
		return Number.isSafeInteger(n) ? n : v;
	});
	// float4, float8
	types.setTypeParser(700, v => (v === null ? null : parseFloat(v)));
	types.setTypeParser(701, v => (v === null ? null : parseFloat(v)));
} catch {}

// Transient error codes that should trigger a retry
const TRANSIENT_ERROR_CODES = new Set([
	'ECONNRESET',      // Connection reset
	'ECONNREFUSED',    // Connection refused
	'ETIMEDOUT',       // Connection timed out
	'EPIPE',           // Broken pipe
	'57P01',           // admin_shutdown - terminating connection due to administrator command
	'57P02',           // crash_shutdown
	'57P03',           // cannot_connect_now
	'08000',           // connection_exception
	'08003',           // connection_does_not_exist
	'08006',           // connection_failure
	'08001',           // sqlclient_unable_to_establish_sqlconnection
	'08004',           // sqlserver_rejected_establishment_of_sqlconnection
	'08007',           // transaction_resolution_unknown
	'08P01',           // protocol_violation
	'XX000',           // internal_error (can be transient)
]);

// Retry configuration
const MAX_RETRIES = 3;
const INITIAL_RETRY_DELAY_MS = 100;
const MAX_RETRY_DELAY_MS = 2000;

/**
 * Check if an error is transient and should trigger a retry
 */
function isTransientError(err) {
	if (!err) return false;

	// Check PostgreSQL error codes
	if (err.code && TRANSIENT_ERROR_CODES.has(err.code)) {
		return true;
	}

	// Check Node.js error codes (network errors)
	if (err.errno && TRANSIENT_ERROR_CODES.has(err.errno)) {
		return true;
	}

	// Check error message patterns
	const msg = (err.message || '').toLowerCase();
	if (
		msg.includes('connection terminated') ||
		msg.includes('connection refused') ||
		msg.includes('connection reset') ||
		msg.includes('client has encountered a connection error') ||
		msg.includes('terminating connection due to administrator command') ||
		msg.includes('server closed the connection unexpectedly') ||
		msg.includes('the database system is shutting down') ||
		msg.includes('the database system is starting up') ||
		msg.includes('cannot connect') ||
		msg.includes('network error')
	) {
		return true;
	}

	return false;
}

/**
 * Sleep for a given number of milliseconds
 */
function sleep(ms) {
	return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Create a resilient pool with error handling and query retry logic
 */
function createResilientPool(config, poolName) {
	const p = new Pool(config);

	// Handle pool-level errors to prevent process crashes
	p.on('error', (err, _client) => {
		console.error(`[${poolName}] Pool error (non-fatal):`, err.message || err);
		// The pool will automatically create new connections as needed
		// No need to manually reconnect - pg handles this
	});

	// Log when connections are acquired (useful for debugging)
	p.on('connect', (_client) => {
		if (process.env.SQL_LOG === '1' || process.env.SQL_LOG === 'true') {
			console.log(`[${poolName}] New client connected`);
		}
	});

	// Log when connections are removed
	p.on('remove', (_client) => {
		if (process.env.SQL_LOG === '1' || process.env.SQL_LOG === 'true') {
			console.log(`[${poolName}] Client removed from pool`);
		}
	});

	return p;
}

// Single shared pools for the whole API with error handling
const pool = createResilientPool(credentials.nexus, 'nexus');
const usersPool = createResilientPool(credentials.nexus_users, 'nexus_users');

/**
 * Wrap query to add retry logic, record metrics, and optionally log SQL
 */
function wrapPool(p, poolName) {
	const origQuery = p.query.bind(p);
	const SQL_LOG = (process.env.SQL_LOG === '1' || process.env.SQL_LOG === 'true');
	const SQL_SLOW_MS = parseInt(process.env.SQL_SLOW_MS || '30', 10);

	p.query = async (...args) => {
		let lastError = null;
		let retryCount = 0;

		// Extract SQL text for logging
		let text = '';
		try {
			if (typeof args[0] === 'string') {
				text = args[0];
			} else if (args[0] && typeof args[0] === 'object' && args[0].text) {
				text = args[0].text;
			}
		} catch {}

		while (retryCount <= MAX_RETRIES) {
			const start = process.hrtime.bigint();
			try {
				const res = await origQuery(...args);

				// Log successful query metrics
				const durMs = Number(process.hrtime.bigint() - start) / 1e6;
				try { recordQuery(durMs); } catch {}
				if (SQL_LOG || durMs >= SQL_SLOW_MS) {
					const preview = text ? text.replace(/\s+/g, ' ').slice(0, 600) : '[unknown-sql]';
					const paramsCount = Array.isArray(args[1]) ? args[1].length : (args[0] && Array.isArray(args[0].values) ? args[0].values.length : 0);
					const retryInfo = retryCount > 0 ? ` [retry ${retryCount}]` : '';
					console.log('[sql]', `${Math.round(durMs)}ms`, `(${paramsCount} params)${retryInfo}`, preview);
				}

				return res;
			} catch (err) {
				lastError = err;
				const durMs = Number(process.hrtime.bigint() - start) / 1e6;

				// Check if this is a transient error we can retry
				if (isTransientError(err) && retryCount < MAX_RETRIES) {
					retryCount++;
					const delay = Math.min(INITIAL_RETRY_DELAY_MS * Math.pow(2, retryCount - 1), MAX_RETRY_DELAY_MS);
					console.warn(`[${poolName}] Transient error (retry ${retryCount}/${MAX_RETRIES} after ${delay}ms):`, err.message || err.code || err);
					await sleep(delay);
					continue;
				}

				// Log the failed query
				if (SQL_LOG || durMs >= SQL_SLOW_MS) {
					const preview = text ? text.replace(/\s+/g, ' ').slice(0, 600) : '[unknown-sql]';
					console.error(`[${poolName}] Query failed after ${retryCount} retries:`, preview);
				}

				throw err;
			}
		}

		// Should not reach here, but just in case
		throw lastError || new Error('Query failed after max retries');
	};

	return p;
}

wrapPool(pool, 'nexus');
wrapPool(usersPool, 'nexus_users');

/**
 * Health check function to verify database connectivity
 * Returns { nexus: boolean, users: boolean }
 */
async function checkHealth() {
	const results = { nexus: false, users: false };

	try {
		await pool.query('SELECT 1');
		results.nexus = true;
	} catch (err) {
		console.error('[nexus] Health check failed:', err.message);
	}

	try {
		await usersPool.query('SELECT 1');
		results.users = true;
	} catch (err) {
		console.error('[nexus_users] Health check failed:', err.message);
	}

	return results;
}

/**
 * Graceful shutdown - drain pools
 */
async function shutdown() {
	console.log('[db] Shutting down connection pools...');
	await Promise.all([
		pool.end().catch(err => console.error('[nexus] Pool end error:', err.message)),
		usersPool.end().catch(err => console.error('[nexus_users] Pool end error:', err.message)),
	]);
	console.log('[db] Connection pools closed');
}

module.exports = { pool, usersPool, checkHealth, shutdown };
