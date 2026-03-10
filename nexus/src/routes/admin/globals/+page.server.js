// @ts-nocheck
import { pool } from '$lib/server/db.js';
import { requireAdmin } from '$lib/server/auth.js';

export async function load({ locals }) {
  requireAdmin(locals);

  const { rows } = await pool.query(
    `SELECT r.id, r.global_id, r.reason, r.created_at, r.resolved_at, r.resolved_by,
            u.eu_name AS reporter_name,
            g.player_name, g.target_name, g.value, g.media_image_key, g.media_video_url,
            ru.eu_name AS resolved_by_name
     FROM globals_media_reports r
     JOIN users u ON u.id = r.reporter_id
     JOIN ingested_globals g ON g.id = r.global_id
     LEFT JOIN users ru ON ru.id = r.resolved_by
     ORDER BY r.resolved_at IS NULL DESC, r.created_at DESC
     LIMIT 200`
  );

  return {
    reports: rows.map(r => ({
      id: r.id,
      global_id: r.global_id,
      reason: r.reason,
      created_at: r.created_at,
      resolved_at: r.resolved_at,
      reporter_name: r.reporter_name || 'Unknown',
      player_name: r.player_name,
      target_name: r.target_name,
      value: parseFloat(r.value),
      has_image: !!r.media_image_key,
      has_video: !!r.media_video_url,
      resolved_by_name: r.resolved_by_name || null,
    })),
  };
}
