// @ts-nocheck
import { json } from '@sveltejs/kit';
import { validateEntity, hasSchema } from '$lib/server/schemaValidator.js';

const API_BASE = process.env.INTERNAL_API_URL || 'http://api:3000';

/**
 * Proxy for the Express audit endpoint with JSON schema validation.
 * Strips extra properties (Links, $Url, ItemId, expanded references) from entity data.
 *
 * GET /api/admin/audit/:entityType/:entityId
 * GET /api/admin/audit/:entityType/:entityId/original
 * GET /api/admin/audit/:entityType/:entityId/at/:timestamp
 */
export async function GET({ params, locals, fetch }) {
  const realUser = locals.session?.realUser || locals.session?.user;

  if (!realUser) {
    return json({ error: 'Not authenticated' }, { status: 401 });
  }

  if (!realUser?.grants?.includes('admin.users')) {
    return json({ error: 'Only administrators can access this endpoint' }, { status: 403 });
  }

  const { entityType, entityId } = params;
  const path = params.path || '';

  const targetPath = path ? `/audit/${entityType}/${entityId}/${path}` : `/audit/${entityType}/${entityId}`;
  const targetUrl = `${API_BASE}${targetPath}`;

  let response;
  try {
    response = await fetch(targetUrl);
  } catch (err) {
    return json({ error: 'Failed to reach audit API' }, { status: 502 });
  }

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({ error: 'Audit API error' }));
    return json(errorData, { status: response.status });
  }

  const data = await response.json();

  // Apply schema validation to strip extra properties
  try {
    if (hasSchema(entityType)) {
      if (data.original?.Data) {
        data.original.Data = validateEntity(entityType, data.original.Data);
      }
      if (data.history) {
        for (const entry of data.history) {
          if (entry.Data) {
            entry.Data = validateEntity(entityType, entry.Data);
          }
        }
      }
      if (data.version?.Data) {
        data.version.Data = validateEntity(entityType, data.version.Data);
      }
    }
  } catch (err) {
    // Validation failed — return unvalidated data rather than failing
  }

  return json(data);
}
