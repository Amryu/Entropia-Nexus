# OAuth 2.0 API Access

Entropia Nexus supports OAuth 2.0 Authorization Code flow with PKCE, allowing external applications to access APIs on behalf of users.

## Client Types

Entropia Nexus supports two OAuth client types per [RFC 6749 Section 2.1](https://tools.ietf.org/html/rfc6749#section-2.1):

**Confidential clients** (default) — Server-side applications that can securely store a client secret. The `client_secret` parameter is required when exchanging codes and refreshing tokens. Use for backend web applications, Discord bots, etc.

**Public clients** — Browser-based (SPA) or native applications that cannot securely store a secret. These rely on PKCE alone for security. The `client_secret` parameter must be omitted. Use for apps where source code is accessible to users.

| Feature | Confidential | Public |
|---------|-------------|--------|
| Client secret | Generated on creation | None |
| Token exchange | Requires `client_secret` | PKCE only |
| Token refresh | Requires `client_secret` | `client_id` only |
| Secret rotation | Available | N/A |

Client type is chosen at creation and cannot be changed.

## Quick Start

1. Register an application at `/account/developers`
2. Choose your client type (confidential or public)
3. Redirect users to the authorization endpoint
4. Exchange the authorization code for tokens
5. Use the access token to call APIs

## Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/oauth/authorize` | GET | Start authorization flow |
| `/api/oauth/token` | POST | Exchange code for tokens / refresh tokens |
| `/api/oauth/revoke` | POST | Revoke a token (RFC 7009) |
| `/api/oauth/userinfo` | GET | Get user profile (requires `profile:read`) |
| `/api/oauth/clients` | GET/POST | List/create OAuth clients |
| `/api/oauth/clients/[id]` | GET/PUT/DELETE | Manage a client |
| `/api/oauth/clients/[id]/rotate-secret` | POST | Rotate client secret |
| `/api/oauth/authorizations` | GET | List authorized apps |
| `/api/oauth/authorizations/[clientId]` | DELETE | Revoke app authorization |

## Authorization Flow

### 1. Redirect to Authorization

```
GET /api/oauth/authorize?
  response_type=code&
  client_id=YOUR_CLIENT_ID&
  redirect_uri=https://yourapp.com/callback&
  scope=inventory:read loadouts:read&
  state=RANDOM_STATE&
  code_challenge=BASE64URL_SHA256_OF_VERIFIER&
  code_challenge_method=S256
```

**Parameters:**
- `response_type` - Must be `code`
- `client_id` - Your application's client ID
- `redirect_uri` - Must exactly match a registered redirect URI
- `scope` - Space-separated list of requested scopes
- `state` - Random string for CSRF protection (returned in callback)
- `code_challenge` - PKCE challenge: `base64url(sha256(code_verifier))`
- `code_challenge_method` - Must be `S256`

The user will see a consent page listing the requested permissions and can authorize or deny.

### 2. Handle Callback

On approval, the user is redirected to:
```
https://yourapp.com/callback?code=AUTH_CODE&state=RANDOM_STATE
```

On denial:
```
https://yourapp.com/callback?error=access_denied&state=RANDOM_STATE
```

### 3. Exchange Code for Tokens

```
POST /api/oauth/token
Content-Type: application/x-www-form-urlencoded

grant_type=authorization_code&
code=AUTH_CODE&
client_id=YOUR_CLIENT_ID&
client_secret=YOUR_CLIENT_SECRET&    # confidential clients only
redirect_uri=https://yourapp.com/callback&
code_verifier=ORIGINAL_CODE_VERIFIER
```

**Response:**
```json
{
  "access_token": "...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "refresh_token": "...",
  "scope": "inventory:read loadouts:read"
}
```

### 4. Use the Access Token

```
GET /api/users/inventory
Authorization: Bearer ACCESS_TOKEN
```

### 5. Refresh the Token

Access tokens expire after 1 hour. Use the refresh token to get a new pair:

```
POST /api/oauth/token
Content-Type: application/x-www-form-urlencoded

grant_type=refresh_token&
refresh_token=REFRESH_TOKEN&
client_id=YOUR_CLIENT_ID&
client_secret=YOUR_CLIENT_SECRET    # confidential clients only
```

Refresh tokens are single-use (rotation). Each refresh returns a new access + refresh token pair.

## PKCE (Proof Key for Code Exchange)

PKCE is **required** for all clients (S256 method only).

```javascript
// Generate code verifier (random string, 43-128 chars)
const verifier = crypto.randomBytes(32).toString('hex');

// Generate code challenge
const challenge = crypto
  .createHash('sha256')
  .update(verifier)
  .digest('base64url');
```

## Scopes

| Scope | Description | Required Grant |
|-------|-------------|---------------|
| `profile:read` | Read user profile | - |
| `inventory:read` | Read inventory | - |
| `inventory:write` | Modify inventory | - |
| `loadouts:read` | Read loadouts | - |
| `loadouts:write` | Create/modify loadouts | - |
| `itemsets:read` | Read item sets | - |
| `itemsets:write` | Create/modify item sets | - |
| `skills:read` | Read skill data | - |
| `skills:write` | Import skill data | - |
| `exchange:read` | Read exchange orders | - |
| `exchange:write` | Create/edit/close orders | - |
| `trades:read` | Read trade requests | `market.trade` |
| `trades:write` | Create trade requests | `market.trade` |
| `services:read` | Read services/requests | - |
| `services:write` | Modify services | - |
| `auction:read` | Read auctions/bids | - |
| `auction:write` | Create auctions, bid, settle | - |
| `rental:read` | Read rental data | - |
| `rental:write` | Create/modify rentals | - |
| `notifications:read` | Read notifications | - |
| `notifications:write` | Mark notifications read | - |
| `preferences:read` | Read preferences | - |
| `preferences:write` | Modify preferences | - |
| `societies:read` | Read society data | - |
| `societies:write` | Join/manage societies | - |
| `wiki:read` | Read wiki changes | `wiki.edit` |
| `wiki:write` | Submit wiki changes | `wiki.edit` |
| `guides:write` | Create/edit guides | `guide.create` |
| `uploads:write` | Upload images | - |

Scopes with a "Required Grant" column require the user to have that grant. If the user doesn't have it, the scope is silently excluded from the token.

## Security

- **Tokens are hashed** - Only SHA-256 hashes stored; raw tokens returned once
- **PKCE required** - Prevents authorization code interception
- **Redirect URI exact match** - No wildcards or partial matching
- **Refresh token rotation** - Each refresh token is single-use; reuse triggers full revocation
- **Admin scopes excluded** - Admin grants are never available via OAuth
- **CORS** - Cross-origin requests are allowed for Bearer-authenticated API calls

## Rate Limits

OAuth requests are subject to:
- Existing per-user rate limits (same as browser sessions)
- Additional per-client rate limits

## Token Lifetimes

| Token | Lifetime |
|-------|----------|
| Authorization code | 5 minutes |
| Access token | 1 hour |
| Refresh token | 30 days |

## Client Management

- Maximum 10 applications per user
- Only verified users can register applications
- Client type (confidential or public) is chosen at creation and cannot be changed
- Confidential client secrets can be rotated at `/account/developers`
- Users can view and revoke authorized apps at `/account/authorizations`

## Error Responses

OAuth error responses follow the standard format:
```json
{
  "error": "error_code",
  "error_description": "Human-readable description"
}
```

Common error codes:
- `invalid_request` - Missing or invalid parameters
- `invalid_client` - Unknown client_id
- `invalid_grant` - Invalid/expired code or refresh token
- `invalid_scope` - Unknown scope requested
- `access_denied` - User denied authorization
- `unsupported_grant_type` - Only authorization_code and refresh_token supported
