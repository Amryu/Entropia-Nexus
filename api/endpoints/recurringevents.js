const { pool } = require('./dbClient');
const { withCache } = require('./responseCache');

const queries = {
  All: `SELECT re.*, (
    SELECT COUNT(*)::int FROM "MobSpawns" ms WHERE ms."RecurringEventId" = re."Id"
  ) AS "LinkedMobAreas"
  FROM "RecurringEvents" re ORDER BY re."Name"`
};

function formatRecurringEvent(x) {
  return {
    Id: x.Id,
    Name: x.Name,
    Description: x.Description,
    Color: x.Color,
    LinkedMobAreas: x.LinkedMobAreas ?? 0
  };
}

async function getRecurringEvents() {
  const { rows } = await pool.query(queries.All);
  return rows.map(formatRecurringEvent);
}

function register(app) {
  app.get('/recurringevents', async (req, res) => {
    try {
      res.json(await withCache('/recurringevents', ['RecurringEvents', 'MobSpawns'], getRecurringEvents));
    } catch (err) {
      console.error('Error fetching recurring events:', err);
      res.status(500).json({ error: 'Failed to fetch recurring events' });
    }
  });

  app.post('/recurringevents', async (req, res) => {
    try {
      const { Name, Description, Color } = req.body || {};
      if (!Name?.trim()) return res.status(400).json({ error: 'Name is required' });
      if (Name.trim().length > 100) return res.status(400).json({ error: 'Name must be 100 characters or less' });
      if (Color && !/^#[0-9a-fA-F]{6}$/.test(Color)) return res.status(400).json({ error: 'Color must be a hex color (e.g. #ff6b35)' });

      const { rows } = await pool.query(
        `INSERT INTO "RecurringEvents" ("Name", "Description", "Color")
         VALUES ($1, $2, $3) RETURNING *`,
        [Name.trim(), Description?.trim() || null, Color || '#ff6b35']
      );
      res.status(201).json(formatRecurringEvent(rows[0]));
    } catch (err) {
      if (err.code === '23505') return res.status(409).json({ error: 'A recurring event with that name already exists' });
      console.error('Error creating recurring event:', err);
      res.status(500).json({ error: 'Failed to create recurring event' });
    }
  });

  app.put('/recurringevents/:id', async (req, res) => {
    try {
      const id = parseInt(req.params.id, 10);
      if (isNaN(id)) return res.status(400).json({ error: 'Invalid ID' });

      const { Name, Description, Color } = req.body || {};
      const sets = [];
      const values = [];
      let idx = 1;

      if (Name !== undefined) {
        if (!Name?.trim()) return res.status(400).json({ error: 'Name is required' });
        if (Name.trim().length > 100) return res.status(400).json({ error: 'Name must be 100 characters or less' });
        sets.push(`"Name" = $${idx++}`);
        values.push(Name.trim());
      }
      if (Description !== undefined) {
        sets.push(`"Description" = $${idx++}`);
        values.push(Description?.trim() || null);
      }
      if (Color !== undefined) {
        if (Color && !/^#[0-9a-fA-F]{6}$/.test(Color)) return res.status(400).json({ error: 'Color must be a hex color (e.g. #ff6b35)' });
        sets.push(`"Color" = $${idx++}`);
        values.push(Color || '#ff6b35');
      }

      if (sets.length === 0) return res.status(400).json({ error: 'No fields to update' });

      values.push(id);
      const { rows } = await pool.query(
        `UPDATE "RecurringEvents" SET ${sets.join(', ')} WHERE "Id" = $${idx} RETURNING *`,
        values
      );
      if (rows.length === 0) return res.status(404).json({ error: 'Recurring event not found' });
      res.json(formatRecurringEvent(rows[0]));
    } catch (err) {
      if (err.code === '23505') return res.status(409).json({ error: 'A recurring event with that name already exists' });
      console.error('Error updating recurring event:', err);
      res.status(500).json({ error: 'Failed to update recurring event' });
    }
  });

  app.delete('/recurringevents/:id', async (req, res) => {
    try {
      const id = parseInt(req.params.id, 10);
      if (isNaN(id)) return res.status(400).json({ error: 'Invalid ID' });

      // Check for linked mob areas
      const { rows: linked } = await pool.query(
        `SELECT COUNT(*)::int AS count FROM "MobSpawns" WHERE "RecurringEventId" = $1`, [id]
      );
      if (linked[0].count > 0) {
        return res.status(409).json({ error: `Cannot delete: ${linked[0].count} mob area(s) are linked to this event` });
      }

      const { rowCount } = await pool.query(`DELETE FROM "RecurringEvents" WHERE "Id" = $1`, [id]);
      if (rowCount === 0) return res.status(404).json({ error: 'Recurring event not found' });
      res.json({ success: true });
    } catch (err) {
      console.error('Error deleting recurring event:', err);
      res.status(500).json({ error: 'Failed to delete recurring event' });
    }
  });
}

module.exports = { register, getRecurringEvents };
