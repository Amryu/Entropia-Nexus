// @ts-nocheck
import { pool } from '$lib/server/db.js';

const INITIAL_LIMIT = 50;

export async function load() {
  try {
    const [globalsResult, statsResult] = await Promise.all([
      pool.query(
        `SELECT id, global_type, player_name, target_name, value, value_unit,
                location, is_hof, is_ath, event_timestamp,
                mob_id, maturity_id, extra
         FROM ingested_globals
         WHERE confirmed = true
         ORDER BY event_timestamp DESC
         LIMIT $1`,
        [INITIAL_LIMIT]
      ),
      pool.query(
        `SELECT count(*) AS total_count,
                COALESCE(sum(value), 0) AS total_value,
                count(*) FILTER (WHERE is_hof) AS hof_count,
                count(*) FILTER (WHERE is_ath) AS ath_count
         FROM ingested_globals
         WHERE confirmed = true`
      ),
    ]);

    const globals = globalsResult.rows.map(r => ({
      id: r.id,
      type: r.global_type,
      player: r.player_name,
      target: r.target_name,
      value: parseFloat(r.value),
      unit: r.value_unit,
      location: r.location,
      hof: r.is_hof,
      ath: r.is_ath,
      timestamp: r.event_timestamp,
      mob_id: r.mob_id,
      maturity_id: r.maturity_id,
      extra: r.extra,
    }));

    const s = statsResult.rows[0];
    const summary = {
      total_count: parseInt(s.total_count),
      total_value: parseFloat(s.total_value),
      hof_count: parseInt(s.hof_count),
      ath_count: parseInt(s.ath_count),
    };

    return { globals, summary };
  } catch {
    return { globals: [], summary: { total_count: 0, total_value: 0, hof_count: 0, ath_count: 0 } };
  }
}
