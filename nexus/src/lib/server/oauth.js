// @ts-nocheck
import crypto from 'crypto';
import { pool } from './db.js';
import { resolveUserGrants } from './grants.js';

// --- Constants ---

export const ACCESS_TOKEN_EXPIRY_SECONDS = 60 * 60;             // 1 hour
export const REFRESH_TOKEN_EXPIRY_SECONDS = 60 * 60 * 24 * 30;  // 30 days
export const AUTH_CODE_EXPIRY_SECONDS = 60 * 5;                  // 5 minutes
export const MAX_CLIENTS_PER_USER = 10;

// --- Token utilities ---

/**
 * Generate a cryptographically random token (hex string).
 * @returns {string} 64-character hex token
 */
export function generateToken() {
  return crypto.randomBytes(32).toString('hex');
}

/**
 * SHA-256 hash a raw token for storage.
 * @param {string} raw - The raw token value
 * @returns {string} Hex-encoded SHA-256 hash
 */
export function hashToken(raw) {
  return crypto.createHash('sha256').update(raw).digest('hex');
}

/**
 * Verify a PKCE S256 code verifier against a stored challenge.
 * @param {string} verifier - The code_verifier from the client
 * @param {string} challenge - The stored code_challenge
 * @returns {boolean}
 */
export function verifyPKCE(verifier, challenge) {
  const computed = crypto
    .createHash('sha256')
    .update(verifier)
    .digest('base64url');
  return computed === challenge;
}

// --- Scope helpers ---

/** @type {Map<string, { description: string, grant_keys: string[] }>} */
let scopeCache = null;
let scopeCacheAt = 0;
const SCOPE_CACHE_TTL = 60_000; // 1 minute

/**
 * Load all scope definitions from DB (cached).
 * @returns {Promise<Map<string, { description: string, grant_keys: string[] }>>}
 */
export async function getScopeDefinitions() {
  const now = Date.now();
  if (scopeCache && now - scopeCacheAt < SCOPE_CACHE_TTL) return scopeCache;

  const { rows } = await pool.query('SELECT key, description, grant_keys FROM oauth_scopes ORDER BY key');
  const map = new Map();
  for (const row of rows) {
    map.set(row.key, { description: row.description, grant_keys: row.grant_keys || [] });
  }
  scopeCache = map;
  scopeCacheAt = now;
  return map;
}

/**
 * Validate requested scopes against user grants.
 * Returns the subset of scopes the user is allowed to use.
 * @param {string[]} requestedScopes - Scopes requested by the client
 * @param {Set<string>} userGrants - User's resolved grants
 * @returns {Promise<string[]>} Effective scopes
 */
export async function validateScopes(requestedScopes, userGrants) {
  const definitions = await getScopeDefinitions();
  const effective = [];

  for (const scope of requestedScopes) {
    const def = definitions.get(scope);
    if (!def) continue; // Unknown scope, skip

    // Check if user has all required grants for this scope
    const requiredGrants = def.grant_keys;
    if (requiredGrants.length === 0 || requiredGrants.every(g => userGrants.has(g))) {
      effective.push(scope);
    }
  }

  return effective;
}

/**
 * Get the set of grant keys that are allowed by the given scopes.
 * Used to filter user.grants to only scope-allowed grants.
 * @param {string[]} scopes - Active OAuth scopes
 * @returns {Promise<Set<string>>} Set of allowed grant keys
 */
export async function getGrantKeysForScopes(scopes) {
  const definitions = await getScopeDefinitions();
  const grantKeys = new Set();

  for (const scope of scopes) {
    const def = definitions.get(scope);
    if (def) {
      for (const key of def.grant_keys) {
        grantKeys.add(key);
      }
    }
  }

  return grantKeys;
}

// --- Client management ---

/**
 * Create a new OAuth client.
 * @param {bigint} userId - Owner user ID
 * @param {string} name - Client display name
 * @param {string} [description] - Client description
 * @param {string} [websiteUrl] - Client website URL
 * @param {string[]} redirectUris - Allowed redirect URIs
 * @param {boolean} [isConfidential=true] - Whether client is confidential
 * @returns {Promise<{ clientId: string, clientSecret: string }>}
 */
export async function createClient(userId, name, description, websiteUrl, redirectUris, isConfidential = true) {
  // Check client limit
  const { rows: countRows } = await pool.query(
    'SELECT COUNT(*) AS count FROM oauth_clients WHERE user_id = $1',
    [userId]
  );
  if (parseInt(countRows[0].count) >= MAX_CLIENTS_PER_USER) {
    throw new Error(`Maximum of ${MAX_CLIENTS_PER_USER} OAuth clients per user.`);
  }

  const clientId = crypto.randomUUID();
  const clientSecret = generateToken();
  const secretHash = hashToken(clientSecret);

  await pool.query(
    `INSERT INTO oauth_clients (id, secret_hash, user_id, name, description, website_url, redirect_uris, is_confidential)
     VALUES ($1, $2, $3, $4, $5, $6, $7, $8)`,
    [clientId, secretHash, userId, name, description || null, websiteUrl || null, redirectUris, isConfidential]
  );

  return { clientId, clientSecret };
}

/**
 * Get a client by ID.
 * @param {string} clientId
 * @returns {Promise<object|null>}
 */
export async function getClient(clientId) {
  const { rows } = await pool.query(
    'SELECT id, user_id, name, description, website_url, redirect_uris, is_confidential, created_at, updated_at FROM oauth_clients WHERE id = $1',
    [clientId]
  );
  return rows[0] || null;
}

/**
 * Get all clients owned by a user.
 * @param {bigint} userId
 * @returns {Promise<object[]>}
 */
export async function getClientsByUser(userId) {
  const { rows } = await pool.query(
    'SELECT id, name, description, website_url, redirect_uris, is_confidential, created_at, updated_at FROM oauth_clients WHERE user_id = $1 ORDER BY created_at DESC',
    [userId]
  );
  return rows;
}

/**
 * Update a client (only if owned by user).
 * @param {string} clientId
 * @param {bigint} userId
 * @param {{ name?: string, description?: string, websiteUrl?: string, redirectUris?: string[] }} updates
 * @returns {Promise<boolean>} Whether the update was applied
 */
export async function updateClient(clientId, userId, updates) {
  const sets = [];
  const params = [clientId, userId];
  let i = 3;

  if (updates.name !== undefined) { sets.push(`name = $${i++}`); params.push(updates.name); }
  if (updates.description !== undefined) { sets.push(`description = $${i++}`); params.push(updates.description); }
  if (updates.websiteUrl !== undefined) { sets.push(`website_url = $${i++}`); params.push(updates.websiteUrl); }
  if (updates.redirectUris !== undefined) { sets.push(`redirect_uris = $${i++}`); params.push(updates.redirectUris); }

  if (sets.length === 0) return false;

  sets.push(`updated_at = now()`);

  const { rowCount } = await pool.query(
    `UPDATE oauth_clients SET ${sets.join(', ')} WHERE id = $1 AND user_id = $2`,
    params
  );
  return rowCount > 0;
}

/**
 * Delete a client and all associated tokens (cascade).
 * @param {string} clientId
 * @param {bigint} userId
 * @returns {Promise<boolean>}
 */
export async function deleteClient(clientId, userId) {
  const { rowCount } = await pool.query(
    'DELETE FROM oauth_clients WHERE id = $1 AND user_id = $2',
    [clientId, userId]
  );
  return rowCount > 0;
}

/**
 * Verify a client secret.
 * @param {string} clientId
 * @param {string} secret - Raw client secret
 * @returns {Promise<boolean>}
 */
export async function verifyClientSecret(clientId, secret) {
  const { rows } = await pool.query(
    'SELECT secret_hash FROM oauth_clients WHERE id = $1',
    [clientId]
  );
  if (!rows[0]) return false;
  return rows[0].secret_hash === hashToken(secret);
}

/**
 * Rotate a client's secret (only if owned by user).
 * @param {string} clientId
 * @param {bigint} userId
 * @returns {Promise<string|null>} New raw client secret, or null if not found
 */
export async function rotateClientSecret(clientId, userId) {
  const newSecret = generateToken();
  const newHash = hashToken(newSecret);

  const { rowCount } = await pool.query(
    'UPDATE oauth_clients SET secret_hash = $3, updated_at = now() WHERE id = $1 AND user_id = $2',
    [clientId, userId, newHash]
  );

  return rowCount > 0 ? newSecret : null;
}

// --- Authorization codes ---

/**
 * Create an authorization code.
 * @param {string} clientId
 * @param {bigint} userId
 * @param {string} redirectUri
 * @param {string[]} scopes
 * @param {string} codeChallenge - PKCE S256 challenge
 * @returns {Promise<string>} Raw authorization code
 */
export async function createAuthorizationCode(clientId, userId, redirectUri, scopes, codeChallenge) {
  const rawCode = generateToken();
  const codeHash = hashToken(rawCode);
  const expiresAt = new Date(Date.now() + AUTH_CODE_EXPIRY_SECONDS * 1000);

  await pool.query(
    `INSERT INTO oauth_authorization_codes (code, client_id, user_id, redirect_uri, scopes, code_challenge, code_challenge_method, expires_at)
     VALUES ($1, $2, $3, $4, $5, $6, 'S256', $7)`,
    [codeHash, clientId, userId, redirectUri, scopes, codeChallenge, expiresAt]
  );

  return rawCode;
}

/**
 * Exchange an authorization code for tokens.
 * @param {string} rawCode - The raw authorization code
 * @param {string} clientId
 * @param {string|null} clientSecret - null for public clients
 * @param {string} redirectUri
 * @param {string} codeVerifier - PKCE code verifier
 * @returns {Promise<{ accessToken: string, refreshToken: string, expiresIn: number, scope: string }|null>}
 */
export async function exchangeAuthorizationCode(rawCode, clientId, clientSecret, redirectUri, codeVerifier) {
  const codeHash = hashToken(rawCode);

  // Fetch and validate the authorization code
  const { rows } = await pool.query(
    `SELECT * FROM oauth_authorization_codes WHERE code = $1`,
    [codeHash]
  );

  const authCode = rows[0];
  if (!authCode) return null;

  // Mark as used immediately (single-use)
  await pool.query(
    'UPDATE oauth_authorization_codes SET used = true WHERE code = $1',
    [codeHash]
  );

  // Validate
  if (authCode.used) return null;
  if (new Date(authCode.expires_at) < new Date()) return null;
  if (authCode.client_id !== clientId) return null;
  if (authCode.redirect_uri !== redirectUri) return null;

  // Verify PKCE
  if (!verifyPKCE(codeVerifier, authCode.code_challenge)) return null;

  // Verify client secret for confidential clients
  const client = await getClient(clientId);
  if (!client) return null;
  if (client.is_confidential) {
    if (!clientSecret || !(await verifyClientSecret(clientId, clientSecret))) return null;
  }

  // Generate tokens
  const rawAccessToken = generateToken();
  const rawRefreshToken = generateToken();
  const accessTokenHash = hashToken(rawAccessToken);
  const refreshTokenHash = hashToken(rawRefreshToken);
  const accessExpiresAt = new Date(Date.now() + ACCESS_TOKEN_EXPIRY_SECONDS * 1000);
  const refreshExpiresAt = new Date(Date.now() + REFRESH_TOKEN_EXPIRY_SECONDS * 1000);

  await pool.query(
    `INSERT INTO oauth_access_tokens (token_hash, client_id, user_id, scopes, expires_at)
     VALUES ($1, $2, $3, $4, $5)`,
    [accessTokenHash, clientId, authCode.user_id, authCode.scopes, accessExpiresAt]
  );

  await pool.query(
    `INSERT INTO oauth_refresh_tokens (token_hash, access_token_hash, client_id, user_id, scopes, expires_at)
     VALUES ($1, $2, $3, $4, $5, $6)`,
    [refreshTokenHash, accessTokenHash, clientId, authCode.user_id, authCode.scopes, refreshExpiresAt]
  );

  return {
    accessToken: rawAccessToken,
    refreshToken: rawRefreshToken,
    expiresIn: ACCESS_TOKEN_EXPIRY_SECONDS,
    scope: authCode.scopes.join(' ')
  };
}

// --- Token validation ---

/**
 * Validate an access token and return session-like data.
 * @param {string} rawToken - The raw Bearer token
 * @returns {Promise<{ userId: bigint, clientId: string, scopes: string[] }|null>}
 */
export async function validateAccessToken(rawToken) {
  const tokenHash = hashToken(rawToken);

  const { rows } = await pool.query(
    `SELECT user_id, client_id, scopes FROM oauth_access_tokens
     WHERE token_hash = $1 AND expires_at > now()`,
    [tokenHash]
  );

  if (!rows[0]) return null;

  return {
    userId: BigInt(rows[0].user_id),
    clientId: rows[0].client_id,
    scopes: rows[0].scopes || []
  };
}

// --- Token refresh ---

/**
 * Refresh an access token using a refresh token (with rotation).
 * If the refresh token has already been used, revoke ALL tokens for the client+user (breach detection).
 * @param {string} rawRefreshToken
 * @param {string} clientId
 * @param {string|null} clientSecret - null for public clients
 * @returns {Promise<{ accessToken: string, refreshToken: string, expiresIn: number, scope: string }|null>}
 */
export async function refreshAccessToken(rawRefreshToken, clientId, clientSecret) {
  const refreshHash = hashToken(rawRefreshToken);

  const { rows } = await pool.query(
    'SELECT * FROM oauth_refresh_tokens WHERE token_hash = $1',
    [refreshHash]
  );

  const refreshRow = rows[0];
  if (!refreshRow) return null;

  // Client must match
  if (refreshRow.client_id !== clientId) return null;

  // Verify client secret for confidential clients
  const client = await getClient(clientId);
  if (!client) return null;
  if (client.is_confidential) {
    if (!clientSecret || !(await verifyClientSecret(clientId, clientSecret))) return null;
  }

  // Reuse detection: if already used, revoke everything for this client+user
  if (refreshRow.used) {
    console.warn(`[oauth] Refresh token reuse detected for client ${clientId}, user ${refreshRow.user_id}. Revoking all tokens.`);
    await revokeAllClientUserTokens(clientId, refreshRow.user_id);
    return null;
  }

  // Check expiry
  if (new Date(refreshRow.expires_at) < new Date()) return null;

  // Mark old refresh token as used
  await pool.query(
    'UPDATE oauth_refresh_tokens SET used = true WHERE token_hash = $1',
    [refreshHash]
  );

  // Delete old access token
  await pool.query(
    'DELETE FROM oauth_access_tokens WHERE token_hash = $1',
    [refreshRow.access_token_hash]
  );

  // Generate new token pair
  const rawAccessToken = generateToken();
  const rawNewRefreshToken = generateToken();
  const accessTokenHash = hashToken(rawAccessToken);
  const newRefreshHash = hashToken(rawNewRefreshToken);
  const accessExpiresAt = new Date(Date.now() + ACCESS_TOKEN_EXPIRY_SECONDS * 1000);
  const refreshExpiresAt = new Date(Date.now() + REFRESH_TOKEN_EXPIRY_SECONDS * 1000);

  await pool.query(
    `INSERT INTO oauth_access_tokens (token_hash, client_id, user_id, scopes, expires_at)
     VALUES ($1, $2, $3, $4, $5)`,
    [accessTokenHash, clientId, refreshRow.user_id, refreshRow.scopes, accessExpiresAt]
  );

  await pool.query(
    `INSERT INTO oauth_refresh_tokens (token_hash, access_token_hash, client_id, user_id, scopes, expires_at)
     VALUES ($1, $2, $3, $4, $5, $6)`,
    [newRefreshHash, accessTokenHash, clientId, refreshRow.user_id, refreshRow.scopes, refreshExpiresAt]
  );

  return {
    accessToken: rawAccessToken,
    refreshToken: rawNewRefreshToken,
    expiresIn: ACCESS_TOKEN_EXPIRY_SECONDS,
    scope: refreshRow.scopes.join(' ')
  };
}

// --- Token revocation ---

/**
 * Revoke a single token (access or refresh).
 * @param {string} rawToken
 */
export async function revokeToken(rawToken) {
  const tokenHash = hashToken(rawToken);

  // Try both tables
  await pool.query('DELETE FROM oauth_access_tokens WHERE token_hash = $1', [tokenHash]);
  await pool.query('DELETE FROM oauth_refresh_tokens WHERE token_hash = $1', [tokenHash]);
}

/**
 * Revoke all tokens for a client+user pair (used for breach detection and authorization revocation).
 * @param {string} clientId
 * @param {bigint|string} userId
 */
export async function revokeAllClientUserTokens(clientId, userId) {
  await pool.query('DELETE FROM oauth_access_tokens WHERE client_id = $1 AND user_id = $2', [clientId, userId]);
  await pool.query('DELETE FROM oauth_refresh_tokens WHERE client_id = $1 AND user_id = $2', [clientId, userId]);
  await pool.query('DELETE FROM oauth_authorization_codes WHERE client_id = $1 AND user_id = $2', [clientId, userId]);
}

// --- User authorization management ---

/**
 * Get all apps a user has authorized (has active tokens for).
 * @param {bigint} userId
 * @returns {Promise<object[]>}
 */
export async function getUserAuthorizations(userId) {
  const { rows } = await pool.query(
    `SELECT DISTINCT ON (c.id)
       c.id AS client_id,
       c.name,
       c.description,
       c.website_url,
       t.scopes,
       t.created_at AS authorized_at
     FROM oauth_access_tokens t
     JOIN oauth_clients c ON c.id = t.client_id
     WHERE t.user_id = $1 AND t.expires_at > now()
     ORDER BY c.id, t.created_at DESC`,
    [userId]
  );
  return rows;
}

// --- Cleanup ---

/**
 * Delete all expired tokens and used authorization codes.
 * Called periodically from hooks.server.js.
 */
export async function cleanupExpiredTokens() {
  const now = new Date();

  await pool.query('DELETE FROM oauth_authorization_codes WHERE expires_at < $1 OR used = true', [now]);
  await pool.query('DELETE FROM oauth_access_tokens WHERE expires_at < $1', [now]);
  await pool.query('DELETE FROM oauth_refresh_tokens WHERE expires_at < $1', [now]);
}
