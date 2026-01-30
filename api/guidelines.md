# Entropia Nexus API Guidelines

## Project Overview

**Framework**: Express.js  
**Language**: JavaScript (Node.js)  
**Database**: PostgreSQL (via pg-promise)  
**Port**: 3000  
**Purpose**: REST API serving Entropia Universe game data from PostgreSQL databases

## Technology Stack

- **Express.js** - Web framework for Node.js
- **pg-promise** - PostgreSQL client for Node.js
- **pg** - Low-level PostgreSQL driver
- **Swagger/OpenAPI** - API documentation
- **CORS** - Cross-origin resource sharing
- **compression** - Response compression (gzip/brotli)
- **body-parser** - Request body parsing
- **dotenv** - Environment configuration
- **nodemon** - Development auto-reload

## Project Structure

```
api/
├── endpoints/              # Modular endpoint definitions
│   ├── index.js           # Central endpoint registry
│   ├── dbClient.js        # Shared database pool
│   ├── weapons.js         # Weapons endpoint + routes
│   ├── armor.js           # Armor endpoint + routes
│   ├── services.js        # Services endpoint + routes
│   ├── utils.js           # Shared utilities
│   └── ...                # Other domain endpoints
├── app.js                 # Main Express application
├── credentials.js         # Database credentials loader
├── metrics.js             # Request metrics tracking
├── package.json
├── .env.example           # Environment template
└── .env                   # Environment variables (not committed)
```

## Coding Guidelines

### General Principles

1. **Endpoint Modularity**: Each domain (weapons, armor, etc.) has its own file
2. **Shared Database Pool**: Use `dbClient.js` for all DB connections
3. **Automatic Error Handling**: Async errors are automatically forwarded to error middleware
4. **Request Timeout**: All requests timeout after 30 seconds (configurable)
5. **Compression**: All responses are compressed
6. **Documentation**: All endpoints documented with Swagger/JSDoc

### File Organization Pattern

Each endpoint file should follow this structure:

```javascript
const { db, usersDb } = require('./dbClient');

/**
 * @swagger
 * /weapons:
 *   get:
 *     summary: Get all weapons
 *     description: Returns a list of all weapons
 *     responses:
 *       200:
 *         description: Success
 */
async function getWeapons(req, res) {
  const weapons = await db.any('SELECT * FROM weapons ORDER BY name');
  res.json(weapons);
}

module.exports = function(app) {
  app.get('/weapons', getWeapons);
  app.get('/weapons/:id', getWeaponById);
};
```

### Database Access

#### Use Shared Pool

```javascript
const { db, usersDb } = require('./dbClient');

// ✅ Good - uses shared pool
const items = await db.any('SELECT * FROM items');

// ❌ Bad - creates new connection
const customDb = pgp(credentials.nexus);
```

#### Query Methods

- `db.any()` - Returns array (0+ rows)
- `db.one()` - Returns single row (errors if 0 or 2+)
- `db.oneOrNone()` - Returns single row or null
- `db.none()` - No return value (INSERT/UPDATE/DELETE)
- `db.multi()` - Multiple queries in one call

#### Parameterized Queries

Always use parameterized queries to prevent SQL injection:

```javascript
// ✅ Good - parameterized
const weapon = await db.one('SELECT * FROM weapons WHERE id = $1', [id]);

// ❌ Bad - SQL injection risk
const weapon = await db.one(`SELECT * FROM weapons WHERE id = ${id}`);
```

#### Named Parameters

Use `$[name]` for better readability:

```javascript
const result = await db.any(
  'SELECT * FROM items WHERE type = $[type] AND tier >= $[minTier]',
  { type: 'weapon', minTier: 5 }
);
```

### Error Handling

#### Async Route Handlers

Errors in async handlers are automatically caught and forwarded:

```javascript
// Automatic error handling (wrapped by app.js)
async function getItem(req, res) {
  const item = await db.one('SELECT * FROM items WHERE id = $1', [req.params.id]);
  res.json(item); // If db.one throws, error middleware handles it
}
```

#### Manual Error Handling

For custom error messages:

```javascript
async function getItem(req, res, next) {
  try {
    const item = await db.oneOrNone('SELECT * FROM items WHERE id = $1', [req.params.id]);
    if (!item) {
      return res.status(404).json({ error: 'Item not found' });
    }
    res.json(item);
  } catch (err) {
    console.error('Database error:', err);
    next(err); // Forward to error middleware
  }
}
```

#### Global Error Middleware

Defined in `app.js`:

```javascript
app.use((err, req, res, next) => {
  console.error('ERROR:', req.method, req.originalUrl, err.message);
  if (!res.headersSent) {
    res.status(500).json({ 
      error: 'Internal server error', 
      message: err.message 
    });
  }
});
```

### Request Validation

1. Validate required parameters early
2. Validate data types and ranges
3. Return 400 Bad Request for invalid input
4. Return 404 Not Found for missing resources

```javascript
async function updateItem(req, res) {
  const { id } = req.params;
  const { name, price } = req.body;
  
  if (!name || typeof price !== 'number') {
    return res.status(400).json({ error: 'Invalid input' });
  }
  
  const result = await db.result(
    'UPDATE items SET name = $1, price = $2 WHERE id = $3',
    [name, price, id]
  );
  
  if (result.rowCount === 0) {
    return res.status(404).json({ error: 'Item not found' });
  }
  
  res.json({ success: true });
}
```

### CORS Configuration

CORS is enabled globally in `app.js`:

```javascript
app.use(cors({
  origin: process.env.CORS_ORIGIN || '*',
  credentials: true
}));
```

Configure allowed origins in `.env`:

```env
CORS_ORIGIN=http://localhost:3001
```

### Response Formatting

#### Success Responses

```javascript
// Single object
res.json({ id: 1, name: 'Item' });

// Array
res.json([{ id: 1 }, { id: 2 }]);

// With metadata
res.json({
  items: [...],
  total: 100,
  page: 1
});
```

#### Error Responses

```javascript
// 400 Bad Request
res.status(400).json({ error: 'Invalid input', details: '...' });

// 404 Not Found
res.status(404).json({ error: 'Resource not found' });

// 500 Internal Server Error (handled by middleware)
next(new Error('Something went wrong'));
```

### Swagger Documentation

Use JSDoc comments for Swagger/OpenAPI:

```javascript
/**
 * @swagger
 * /weapons/{id}:
 *   get:
 *     summary: Get weapon by ID
 *     description: Returns detailed information about a specific weapon
 *     parameters:
 *       - in: path
 *         name: id
 *         required: true
 *         schema:
 *           type: integer
 *         description: Weapon ID
 *     responses:
 *       200:
 *         description: Success
 *         content:
 *           application/json:
 *             schema:
 *               type: object
 *               properties:
 *                 ItemId:
 *                   type: integer
 *                 Name:
 *                   type: string
 *                 Properties:
 *                   type: object
 *       404:
 *         description: Weapon not found
 */
```

Access documentation at: `http://localhost:3000/api-docs`

### Metrics Tracking

Request metrics are automatically tracked in `app.js`:

```javascript
const { recordRequest, snapshotAndReset } = require('./metrics');

app.use((req, res, next) => {
  recordRequest(req, res);
  next();
});

// Access metrics at /metrics
app.get('/metrics', (req, res) => {
  const snapshot = snapshotAndReset();
  res.json(snapshot);
});
```

### Environment Variables

Required variables in `.env`:

```env
# Primary Database (nexus)
NEXUS_DB_USER=nexus
NEXUS_DB_PASS=your_password
NEXUS_DB_HOST=localhost
NEXUS_DB_NAME=nexus
NEXUS_DB_PORT=5432

# Users Database (nexus-users)
USERS_DB_USER=nexus_users
USERS_DB_PASS=your_password
USERS_DB_HOST=localhost
USERS_DB_NAME=nexus_users
USERS_DB_PORT=5432

# API Configuration
PORT=3000
CORS_ORIGIN=http://localhost:3001
ROUTE_TIMEOUT_MS=30000
```

## Development Workflow

### Running Locally

```bash
# Start development server with auto-reload
npm start

# Run without nodemon
node app.js
```

### Testing Endpoints

Use curl, Postman, or the Swagger UI:

```bash
# Get all weapons
curl http://localhost:3000/weapons

# Get specific weapon
curl http://localhost:3000/weapons/123

# With authentication
curl -H "Authorization: Bearer token" http://localhost:3000/shops
```

## Common Patterns

### Filtering and Sorting

```javascript
async function getItems(req, res) {
  const { type, minTier, sortBy = 'name' } = req.query;
  
  let query = 'SELECT * FROM items WHERE 1=1';
  const params = {};
  
  if (type) {
    query += ' AND type = $[type]';
    params.type = type;
  }
  
  if (minTier) {
    query += ' AND tier >= $[minTier]';
    params.minTier = parseInt(minTier);
  }
  
  query += ` ORDER BY ${sortBy}`;
  
  const items = await db.any(query, params);
  res.json(items);
}
```

### Pagination

```javascript
async function getItemsPaginated(req, res) {
  const page = parseInt(req.query.page) || 1;
  const limit = parseInt(req.query.limit) || 50;
  const offset = (page - 1) * limit;
  
  const [items, totalCount] = await db.multi(
    `SELECT * FROM items ORDER BY name LIMIT $[limit] OFFSET $[offset];
     SELECT COUNT(*) FROM items`,
    { limit, offset }
  );
  
  res.json({
    items: items,
    total: totalCount[0].count,
    page,
    pages: Math.ceil(totalCount[0].count / limit)
  });
}
```

### Complex Joins

```javascript
async function getWeaponsWithAmmo(req, res) {
  const weapons = await db.any(`
    SELECT 
      w.*,
      json_agg(json_build_object(
        'id', a.ItemId,
        'name', a.Name,
        'damage', a.Properties->>'Damage'
      )) as compatible_ammo
    FROM weapons w
    LEFT JOIN ammunition a ON a.Properties->>'WeaponType' = w.Properties->>'Type'
    GROUP BY w.ItemId
  `);
  res.json(weapons);
}
```

### Transactions

```javascript
async function transferItems(req, res) {
  const { fromShop, toShop, itemId, quantity } = req.body;
  
  await usersDb.tx(async t => {
    // Remove from source
    await t.none(
      'UPDATE shop_inventory SET quantity = quantity - $1 WHERE shop_id = $2 AND item_id = $3',
      [quantity, fromShop, itemId]
    );
    
    // Add to destination
    await t.none(
      `INSERT INTO shop_inventory (shop_id, item_id, quantity)
       VALUES ($1, $2, $3)
       ON CONFLICT (shop_id, item_id) DO UPDATE SET quantity = quantity + $3`,
      [toShop, itemId, quantity]
    );
  });
  
  res.json({ success: true });
}
```

## Performance Considerations

1. **Indexing**: Ensure frequently queried columns have indexes
2. **Connection Pooling**: Already handled by `dbClient.js`
3. **Compression**: Enabled globally for all responses
4. **Query Optimization**: Use `EXPLAIN ANALYZE` for slow queries
5. **Caching**: Consider Redis for frequently accessed data
6. **Pagination**: Always paginate large result sets

## Security Best Practices

1. **SQL Injection**: Always use parameterized queries
2. **Authentication**: Implement for sensitive endpoints
3. **Rate Limiting**: Consider adding for public APIs
4. **Input Validation**: Validate all user input
5. **Error Messages**: Don't leak sensitive information
6. **HTTPS**: Use in production (handled by reverse proxy)

## Database Schema Awareness

- **nexus**: Static game data (items, maps, mobs, blueprints)
  - Read-only for most operations
  - Updated by admin/bot workflows
  
- **nexus-users**: User-generated data (accounts, shops, services)
  - Read-write for user operations
  - Includes change tracking tables

## Common Pitfalls to Avoid

1. ❌ Creating new database connections instead of using shared pool
2. ❌ Not handling database errors
3. ❌ Using string concatenation for SQL queries
4. ❌ Not validating user input
5. ❌ Returning entire tables without pagination
6. ❌ Not documenting endpoints with Swagger
7. ❌ Forgetting to close transactions

## Deployment

- Use environment variables for all configuration
- Enable compression (already configured)
- Run behind reverse proxy (nginx/Caddy)
- Monitor metrics endpoint
- Set appropriate timeouts
- Use process manager (PM2/systemd)

## Resources

- [Express.js Docs](https://expressjs.com/)
- [pg-promise Docs](https://github.com/vitaly-t/pg-promise)
- [Swagger/OpenAPI Docs](https://swagger.io/docs/)
- Project README: `../README.md`
