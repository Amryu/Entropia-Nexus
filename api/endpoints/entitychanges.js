const { usersPool, pool } = require('./dbClient');
const { entityTypeToTable } = require('./audit');

/**
 * Search for entities that have had change requests
 * @param {Object} options - Search options
 * @param {string} options.query - Search query for entity name (optional)
 * @param {string} options.entityType - Filter by entity type (optional)
 * @param {number} options.limit - Max results (default 50)
 * @param {number} options.offset - Offset for pagination (default 0)
 */
async function searchEntitiesWithChanges({ query, entityType, limit = 50, offset = 0 }) {
  let sql = `
    SELECT
      entity,
      data->>'Id' as entity_id,
      data->>'Name' as entity_name,
      COUNT(*) as change_count,
      MAX(created_at) as last_change,
      MIN(created_at) as first_change
    FROM changes
    WHERE 1=1
  `;
  const params = [];
  let paramIndex = 1;

  if (query) {
    sql += ` AND data->>'Name' ILIKE $${paramIndex}`;
    params.push(`%${query}%`);
    paramIndex++;
  }

  if (entityType) {
    sql += ` AND entity = $${paramIndex}`;
    params.push(entityType);
    paramIndex++;
  }

  sql += `
    GROUP BY entity, data->>'Id', data->>'Name'
    ORDER BY MAX(created_at) DESC
    LIMIT $${paramIndex} OFFSET $${paramIndex + 1}
  `;
  params.push(limit, offset);

  const { rows } = await usersPool.query(sql, params);

  // Also get total count for pagination
  let countSql = `
    SELECT COUNT(DISTINCT (entity, data->>'Id', data->>'Name')) as total
    FROM changes
    WHERE 1=1
  `;
  const countParams = [];
  let countParamIndex = 1;

  if (query) {
    countSql += ` AND data->>'Name' ILIKE $${countParamIndex}`;
    countParams.push(`%${query}%`);
    countParamIndex++;
  }

  if (entityType) {
    countSql += ` AND entity = $${countParamIndex}`;
    countParams.push(entityType);
  }

  const { rows: countRows } = await usersPool.query(countSql, countParams);
  const total = parseInt(countRows[0]?.total || '0', 10);

  return {
    results: rows.map(row => ({
      entityType: row.entity,
      entityId: row.entity_id ? parseInt(row.entity_id, 10) : null,
      entityName: row.entity_name,
      changeCount: parseInt(row.change_count, 10),
      lastChange: row.last_change,
      firstChange: row.first_change
    })),
    total,
    limit,
    offset
  };
}

/**
 * Get all changes for a specific entity
 * @param {string} entityType - The entity type
 * @param {number|string} entityIdOrName - The entity ID or name
 */
async function getChangesForEntity(entityType, entityIdOrName) {
  const isNumeric = /^\d+$/.test(String(entityIdOrName));

  let sql = `
    SELECT
      c.id,
      c.type,
      c.state,
      c.data,
      c.created_at,
      c.reviewed_at,
      c.author_id,
      c.reviewed_by
    FROM changes c
    WHERE c.entity = $1
  `;
  const params = [entityType];

  if (isNumeric) {
    sql += ` AND (c.data->>'Id' = $2 OR c.data->>'Id' = $3)`;
    params.push(String(entityIdOrName), entityIdOrName);
  } else {
    sql += ` AND c.data->>'Name' = $2`;
    params.push(entityIdOrName);
  }

  sql += ` ORDER BY c.created_at ASC`;

  const { rows } = await usersPool.query(sql, params);

  return rows.map(row => ({
    id: row.id,
    type: row.type,
    state: row.state,
    data: row.data,
    createdAt: row.created_at,
    reviewedAt: row.reviewed_at,
    authorId: row.author_id ? String(row.author_id) : null,
    reviewedBy: row.reviewed_by ? String(row.reviewed_by) : null
  }));
}

/**
 * Get available entity types that have changes
 */
async function getEntityTypesWithChanges() {
  const { rows } = await usersPool.query(`
    SELECT entity, COUNT(*) as count
    FROM changes
    GROUP BY entity
    ORDER BY entity
  `);

  return rows.map(row => ({
    entityType: row.entity,
    count: parseInt(row.count, 10)
  }));
}

function register(app) {
  /**
   * @swagger
   * /entity-changes/types:
   *   get:
   *     description: Get list of entity types that have change requests
   *     responses:
   *       '200':
   *         description: List of entity types with counts
   */
  app.get('/entity-changes/types', async (req, res) => {
    try {
      const types = await getEntityTypesWithChanges();
      res.json({ types });
    } catch (err) {
      console.error('[entity-changes] Error fetching types:', err);
      res.status(500).json({ error: 'Failed to fetch entity types' });
    }
  });

  /**
   * @swagger
   * /entity-changes/search:
   *   get:
   *     description: Search for entities with change requests
   *     parameters:
   *       - in: query
   *         name: q
   *         schema:
   *           type: string
   *         description: Search query for entity name
   *       - in: query
   *         name: type
   *         schema:
   *           type: string
   *         description: Filter by entity type
   *       - in: query
   *         name: limit
   *         schema:
   *           type: integer
   *         description: Max results (default 50)
   *       - in: query
   *         name: offset
   *         schema:
   *           type: integer
   *         description: Offset for pagination
   *     responses:
   *       '200':
   *         description: Search results with pagination info
   */
  app.get('/entity-changes/search', async (req, res) => {
    try {
      const { q, type, limit, offset } = req.query;
      const results = await searchEntitiesWithChanges({
        query: q || null,
        entityType: type || null,
        limit: limit ? parseInt(limit, 10) : 50,
        offset: offset ? parseInt(offset, 10) : 0
      });
      res.json(results);
    } catch (err) {
      console.error('[entity-changes] Error searching:', err);
      res.status(500).json({ error: 'Failed to search entities' });
    }
  });

  /**
   * @swagger
   * /entity-changes/{entityType}/{entityIdOrName}:
   *   get:
   *     description: Get all change requests for a specific entity
   *     parameters:
   *       - in: path
   *         name: entityType
   *         schema:
   *           type: string
   *         required: true
   *         description: The entity type (e.g., Weapon, Armor)
   *       - in: path
   *         name: entityIdOrName
   *         schema:
   *           type: string
   *         required: true
   *         description: The entity ID or name
   *     responses:
   *       '200':
   *         description: List of change requests for this entity
   *       '404':
   *         description: No changes found
   */
  app.get('/entity-changes/:entityType/:entityIdOrName', async (req, res) => {
    try {
      const { entityType, entityIdOrName } = req.params;
      const changes = await getChangesForEntity(entityType, entityIdOrName);

      if (changes.length === 0) {
        return res.status(404).json({ error: 'No changes found for this entity' });
      }

      res.json({
        entityType,
        entityId: /^\d+$/.test(entityIdOrName) ? parseInt(entityIdOrName, 10) : null,
        entityName: changes[0]?.data?.Name || entityIdOrName,
        changes
      });
    } catch (err) {
      console.error('[entity-changes] Error fetching changes:', err);
      res.status(500).json({ error: 'Failed to fetch entity changes' });
    }
  });
}

module.exports = { register, searchEntitiesWithChanges, getChangesForEntity, getEntityTypesWithChanges };
