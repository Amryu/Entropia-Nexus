//@ts-nocheck
import { pool } from './db.js';

/**
 * Get a user's stored skill values.
 * @param {number} userId
 * @returns {Promise<{skills: Object, updated_at: string}|null>}
 */
export async function getUserSkills(userId) {
  const { rows } = await pool.query(
    `SELECT skills, updated_at FROM user_skills WHERE user_id = $1`,
    [userId]
  );
  return rows[0] || null;
}

/**
 * Upsert a user's skill values.
 * @param {number} userId
 * @param {Object<string, number>} skills
 */
export async function upsertUserSkills(userId, skills) {
  await pool.query(
    `INSERT INTO user_skills (user_id, skills, updated_at)
     VALUES ($1, $2, NOW())
     ON CONFLICT (user_id)
     DO UPDATE SET skills = $2, updated_at = NOW()`,
    [userId, JSON.stringify(skills)]
  );
}

/**
 * Create a skill import record with deltas.
 * @param {number} userId
 * @param {Object<string, number>} oldSkills - previous skill values (empty object if first import)
 * @param {Object<string, number>} newSkills - new skill values
 * @returns {Promise<{id: number, summary: Object}>}
 */
export async function createSkillImport(userId, oldSkills, newSkills) {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');

    // Compute diff
    const deltas = [];
    let changed = 0;
    let added = 0;
    let unchanged = 0;
    let totalValue = 0;

    for (const [name, newVal] of Object.entries(newSkills)) {
      const oldVal = oldSkills[name] ?? 0;
      totalValue += newVal;

      if (oldVal !== newVal) {
        deltas.push({ skill_name: name, old_value: oldVal, new_value: newVal });
        if (oldVal === 0 && newVal > 0) added++;
        else changed++;
      } else {
        unchanged++;
      }
    }

    const summary = { changed, added, unchanged };
    const skillCount = Object.keys(newSkills).filter(k => newSkills[k] > 0).length;

    // Insert import record
    const { rows } = await client.query(
      `INSERT INTO skill_imports (user_id, skill_count, total_value, summary)
       VALUES ($1, $2, $3, $4)
       RETURNING id, imported_at`,
      [userId, skillCount, totalValue, JSON.stringify(summary)]
    );
    const importRecord = rows[0];

    // Insert deltas
    if (deltas.length > 0) {
      const values = [];
      const params = [];
      let idx = 1;
      for (const d of deltas) {
        values.push(`($${idx++}, $${idx++}, $${idx++}, $${idx++})`);
        params.push(importRecord.id, d.skill_name, d.old_value, d.new_value);
      }
      await client.query(
        `INSERT INTO skill_import_deltas (import_id, skill_name, old_value, new_value)
         VALUES ${values.join(', ')}`,
        params
      );
    }

    // Update current skills
    await client.query(
      `INSERT INTO user_skills (user_id, skills, updated_at)
       VALUES ($1, $2, NOW())
       ON CONFLICT (user_id)
       DO UPDATE SET skills = $2, updated_at = NOW()`,
      [userId, JSON.stringify(newSkills)]
    );

    await client.query('COMMIT');

    return {
      id: importRecord.id,
      imported_at: importRecord.imported_at,
      skill_count: skillCount,
      total_value: totalValue,
      summary
    };
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
}

/**
 * Get skill import history for a user.
 * @param {number} userId
 * @param {number} [limit=20]
 * @param {number} [offset=0]
 * @returns {Promise<Array>}
 */
export async function getSkillImports(userId, limit = 20, offset = 0) {
  const { rows } = await pool.query(
    `SELECT id, imported_at, skill_count, total_value, summary
     FROM skill_imports
     WHERE user_id = $1
     ORDER BY imported_at DESC
     LIMIT $2 OFFSET $3`,
    [userId, limit, offset]
  );
  return rows;
}

/**
 * Get deltas for a specific import.
 * @param {number} importId
 * @param {number} userId - for authorization check
 * @returns {Promise<Array>}
 */
export async function getSkillImportDeltas(importId, userId) {
  const { rows } = await pool.query(
    `SELECT d.skill_name, d.old_value, d.new_value
     FROM skill_import_deltas d
     JOIN skill_imports i ON i.id = d.import_id
     WHERE d.import_id = $1 AND i.user_id = $2
     ORDER BY d.skill_name ASC`,
    [importId, userId]
  );
  return rows;
}

/**
 * Get skill value history over time (for charts).
 * @param {number} userId
 * @returns {Promise<Array<{imported_at: string, total_value: number}>>}
 */
export async function getSkillValueHistory(userId) {
  const { rows } = await pool.query(
    `SELECT imported_at, total_value
     FROM skill_imports
     WHERE user_id = $1
     ORDER BY imported_at ASC`,
    [userId]
  );
  return rows;
}

/**
 * Get per-skill value history over time (for progression charts).
 * Joins skill_imports with skill_import_deltas to get per-skill snapshots.
 * @param {number} userId
 * @param {{skills?: string[]|null, from?: string|null, to?: string|null}} options
 * @returns {Promise<Array<{imported_at: string, skill_name: string, new_value: number}>>}
 */
export async function getSkillHistory(userId, { skills = null, from = null, to = null } = {}) {
  const params = [userId];
  const conditions = ['i.user_id = $1'];
  let idx = 2;

  if (skills && skills.length > 0) {
    conditions.push(`d.skill_name = ANY($${idx})`);
    params.push(skills);
    idx++;
  }
  if (from) {
    conditions.push(`i.imported_at >= $${idx}::timestamptz`);
    params.push(from);
    idx++;
  }
  if (to) {
    conditions.push(`i.imported_at <= $${idx}::timestamptz`);
    params.push(to);
    idx++;
  }

  const { rows } = await pool.query(
    `SELECT i.imported_at, d.skill_name, d.new_value
     FROM skill_imports i
     JOIN skill_import_deltas d ON d.import_id = i.id
     WHERE ${conditions.join(' AND ')}
     ORDER BY i.imported_at ASC, d.skill_name ASC`,
    params
  );
  return rows;
}

/**
 * Check rate limits for skill imports.
 * @param {number} userId
 * @returns {Promise<{allowed: boolean, reason?: string}>}
 */
export async function checkSkillImportRateLimit(userId) {
  // 5 per minute
  const { rows: perMinute } = await pool.query(
    `SELECT COUNT(*) as cnt FROM skill_imports
     WHERE user_id = $1 AND imported_at > NOW() - INTERVAL '1 minute'`,
    [userId]
  );
  if (Number(perMinute[0].cnt) >= 5) {
    return { allowed: false, reason: 'Rate limit: max 5 imports per minute' };
  }

  // 20 per hour
  const { rows: perHour } = await pool.query(
    `SELECT COUNT(*) as cnt FROM skill_imports
     WHERE user_id = $1 AND imported_at > NOW() - INTERVAL '1 hour'`,
    [userId]
  );
  if (Number(perHour[0].cnt) >= 20) {
    return { allowed: false, reason: 'Rate limit: max 20 imports per hour' };
  }

  return { allowed: true };
}
