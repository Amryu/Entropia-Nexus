//@ts-nocheck
import { requireAdmin } from '$lib/server/auth.js';
import { getIngestionStats, getAlerts, getIngestionUsers, getAllowedClients, getTradeChannels } from '$lib/server/ingestion.js';

export async function load({ locals }) {
  requireAdmin(locals);

  const [stats, alertsResult, users, allowedResult, channelRows] = await Promise.all([
    getIngestionStats(),
    getAlerts(1, 10),
    getIngestionUsers(1, 20),
    getAllowedClients(1, 50),
    getTradeChannels(),
  ]);

  return {
    stats,
    alerts: alertsResult.rows,
    alertTotal: alertsResult.total,
    users,
    allowedClients: allowedResult.rows,
    tradeChannels: channelRows,
  };
}
