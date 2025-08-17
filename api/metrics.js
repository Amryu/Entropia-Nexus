// Simple in-process metrics aggregator (no spam, periodic reporting)
const metrics = {
  since: Date.now(),
  // Requests
  requests: 0,
  requestTimeMs: 0,
  slowRequests: 0,
  byRoute: new Map(), // key: METHOD path → { count, timeMs, slow }
  // DB queries
  queries: 0,
  queryTimeMs: 0,
  slowQueries: 0
};

const REQ_SLOW_MS = parseInt(process.env.REQ_SLOW_MS || '1500', 10);
const SQL_SLOW_MS = parseInt(process.env.SQL_SLOW_MS || '200', 10);

function recordRequest(method, path, durMs) {
  metrics.requests += 1;
  metrics.requestTimeMs += durMs;
  if (durMs >= REQ_SLOW_MS) metrics.slowRequests += 1;
  const key = `${method} ${path}`;
  const cur = metrics.byRoute.get(key) || { count: 0, timeMs: 0, slow: 0 };
  cur.count += 1;
  cur.timeMs += durMs;
  if (durMs >= REQ_SLOW_MS) cur.slow += 1;
  metrics.byRoute.set(key, cur);
}

function recordQuery(durMs) {
  metrics.queries += 1;
  metrics.queryTimeMs += durMs;
  if (durMs >= SQL_SLOW_MS) metrics.slowQueries += 1;
}

function snapshotAndReset() {
  const now = Date.now();
  const elapsedMs = now - metrics.since;
  const snap = {
    since: metrics.since,
    elapsedMs,
    requests: metrics.requests,
    avgReqMs: metrics.requests ? (metrics.requestTimeMs / metrics.requests) : 0,
    slowRequests: metrics.slowRequests,
    queries: metrics.queries,
    avgQueryMs: metrics.queries ? (metrics.queryTimeMs / metrics.queries) : 0,
    slowQueries: metrics.slowQueries,
    byRoute: Array.from(metrics.byRoute.entries())
      .sort((a,b) => b[1].count - a[1].count)
      .slice(0, 10)
      .map(([route, v]) => ({ route, count: v.count, avgMs: v.count ? (v.timeMs / v.count) : 0, slow: v.slow }))
  };
  // Reset counters
  metrics.since = now;
  metrics.requests = 0;
  metrics.requestTimeMs = 0;
  metrics.slowRequests = 0;
  metrics.queries = 0;
  metrics.queryTimeMs = 0;
  metrics.slowQueries = 0;
  metrics.byRoute.clear();
  return snap;
}

module.exports = { metrics, recordRequest, recordQuery, snapshotAndReset };
