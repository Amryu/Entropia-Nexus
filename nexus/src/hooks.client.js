// @ts-nocheck
// Suppress 404s in client error handling; log 5xx with route info
export function handleError({ error, event }) {
  const status = (error && (error.status || error.statusCode)) || 500;
  if (status >= 500 && status < 600) {
    try {
      const routeId = event?.route?.id ?? 'unknown-route';
      const pathname = event?.url?.pathname ?? 'unknown-path';
    const href = event?.url?.href ?? 'unknown-url';
      console.error(`[client ${status}] route: ${routeId} path: ${pathname} url: ${href}`, error);
    } catch (e) {
      console.error(`[client ${status}] error while logging route for error`, e, error);
    }
  }
  return { message: status >= 500 ? 'Internal Server Error' : '' };
}
