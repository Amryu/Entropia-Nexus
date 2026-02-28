//@ts-nocheck
import { requireAdmin } from '$lib/server/auth.js';
import { getIngestionStats, getAlerts, getIngestionUsers, getConflicts, getAllowedClients } from '$lib/server/ingestion.js';

export async function load({ locals }) {
  requireAdmin(locals);

  const [stats, alertsResult, users, conflicts, allowedResult] = await Promise.all([
    getIngestionStats(),
    getAlerts(1, 10),
    getIngestionUsers(1, 20),
    getConflicts(1, 20),
    getAllowedClients(1, 50),
  ]);

  return {
    stats,
    alerts: alertsResult.rows,
    alertTotal: alertsResult.total,
    users,
    conflicts,
    allowedClients: allowedResult.rows,
  };
}
