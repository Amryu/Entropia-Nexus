//@ts-nocheck
import { getChangeById, getChangeEntities as dbGetChangeEntities, getChangeTypes as dbGetChangeTypes, updateChange, deleteChange, createChange, executeVector, getChangeByEntityId, getOpenChangeByEntityId, getChangesFiltered } from "$lib/server/db.js"
import { apiCall, getResponse } from "$lib/util.js";
import sanitizeHtml from "sanitize-html";
import { getValidator } from "$lib/server/schemaValidator.js";

// HTML sanitization config for TipTap rich text editor output
const SANITIZE_CONFIG = {
  allowedTags: [
    'p', 'strong', 'em', 's', 'code', 'br',
    'h1', 'h2', 'h3', 'h4',
    'ul', 'ol', 'li',
    'blockquote', 'pre', 'hr',
    'a',
    'div', 'iframe',
    'img'
  ],
  allowedAttributes: {
    'a': ['href', 'target', 'rel'],
    'div': ['data-type', 'data-provider', 'data-src', 'data-width', 'data-pending', 'data-alt', 'class', 'style'],
    'iframe': ['src', 'width', 'height', 'frameborder', 'allow', 'allowfullscreen'],
    'img': ['src', 'alt', 'data-width', 'data-pending', 'style']
  },
  allowedStyles: {
    '*': { 'width': [/^\d+px$/], 'max-width': [/^\d+(%|px)$/] }
  },
  allowedIframeHostnames: ['www.youtube.com', 'youtube.com', 'player.vimeo.com', 'vimeo.com'],
  transformTags: {
    'a': (tagName, attribs) => ({
      tagName: 'a',
      attribs: { href: attribs.href || '', target: '_blank', rel: 'noopener noreferrer' }
    }),
    'img': (tagName, attribs) => {
      if (!(attribs.src || '').startsWith('/api/img/')) {
        return { tagName: '', attribs: {} };
      }
      return { tagName: 'img', attribs };
    }
  }
};

/**
 * Recursively trims all string values in an object or array.
 */
function trimStrings(obj) {
  if (obj === null || obj === undefined) return obj;
  if (Array.isArray(obj)) {
    for (let i = 0; i < obj.length; i++) {
      if (typeof obj[i] === 'string') obj[i] = obj[i].trim();
      else if (typeof obj[i] === 'object') trimStrings(obj[i]);
    }
  } else if (typeof obj === 'object') {
    for (const key of Object.keys(obj)) {
      if (typeof obj[key] === 'string') obj[key] = obj[key].trim();
      else if (typeof obj[key] === 'object') trimStrings(obj[key]);
    }
  }
  return obj;
}

/**
 * Sanitizes the body: trims all string fields and sanitizes HTML Description fields.
 * This prevents XSS attacks from forged requests bypassing the frontend.
 */
function sanitizeBody(body) {
  // Trim all string fields (Name, Description, nested properties, etc.)
  trimStrings(body);

  if (body && typeof body.Description === 'string') {
    body.Description = sanitizeHtml(body.Description, SANITIZE_CONFIG);
  }
  if (body?.Properties && typeof body.Properties.Description === 'string') {
    body.Properties.Description = sanitizeHtml(body.Properties.Description, SANITIZE_CONFIG);
  }
  // Ensure Set is a valid object for entities that require it (e.g. Clothing)
  if (body && 'Set' in body && !body.Set) {
    body.Set = { Name: null, EffectsOnSetEquip: [] };
  }

  return body;
}

/**
 * Maps schema-based entity names to their DB change_entity enum equivalents.
 * Reverse of ENTITY_TYPE_MAP in schemaValidator.js.
 */
const SCHEMA_TO_ENUM = {
  TeleportationChip: 'TeleportChip',
  Capsule: 'CreatureControlCapsule',
};

function resolveEntityName(name) {
  return SCHEMA_TO_ENUM[name] || name;
}

let change_entities = null;
let change_types = null;


async function getChangeEntities() {
  if (!change_entities) {
    change_entities = await dbGetChangeEntities();
  }

  return change_entities;
}

async function getChangeTypes() {
  if (!change_types) {
    change_types = await dbGetChangeTypes();
  }

  return change_types;
}

export async function GET({ params, url }) {
  // If we have a slug, get single change by ID
  if (params.slug) {
    const change = await getChangeById(params.slug);
    if (!change) {
      // Return 200 with null instead of 404 to avoid console spam
      return new Response(JSON.stringify(null), { status: 200, headers: { 'Content-Type': 'application/json' } });
    }
    return new Response(JSON.stringify(change), { status: 200 });
  }

  // If we have entityId, get single change by entity ID
  if (url.searchParams.get('entityId')) {
    const change = await getChangeByEntityId(url.searchParams.get('entityId'));
    if (!change) {
      // Return 200 with null instead of 404 to avoid console spam
      return new Response(JSON.stringify(null), { status: 200, headers: { 'Content-Type': 'application/json' } });
    }
    return new Response(JSON.stringify(change), { status: 200 });
  }

  // Otherwise, list changes with filters
  const filters = {};

  // Parse entity filter (resolve schema names to DB enum names)
  const entityParam = url.searchParams.get('entity');
  if (entityParam) {
    const validEntities = await getChangeEntities();
    const entityList = entityParam.split(',').map(e => resolveEntityName(e.trim())).filter(Boolean);
    const invalidEntities = entityList.filter(e => !validEntities.includes(e));
    if (invalidEntities.length > 0) {
      return getResponse({ error: `Invalid entity. Must be one of: ${validEntities.join(', ')}` }, 400);
    }
    filters.entity = entityList.join(',');
  }

  // Parse type filter (Create, Update, Delete)
  const type = url.searchParams.get('type');
  if (type) {
    const validTypes = await getChangeTypes();
    const typeList = type.split(',').map(t => t.trim()).filter(Boolean);
    const invalidTypes = typeList.filter(t => !validTypes.includes(t));
    if (invalidTypes.length > 0) {
      return getResponse({ error: `Invalid type. Must be one of: ${validTypes.join(', ')}` }, 400);
    }
    filters.type = type;
  }

  // Parse authorId filter
  const authorId = url.searchParams.get('authorId');
  if (authorId) {
    filters.authorId = authorId;
  }

  // Parse state filter (can be comma-separated)
  const state = url.searchParams.get('state');
  if (state) {
    const states = state.split(',').map(s => s.trim());
    filters.state = states.length === 1 ? states[0] : states;
  }

  // Parse pagination
  const page = parseInt(url.searchParams.get('page') || '1', 10);
  const limit = Math.min(parseInt(url.searchParams.get('limit') || '50', 10), 100);

  const result = await getChangesFiltered(filters, page, limit);

  // Return just the changes array for simpler client usage
  return new Response(JSON.stringify(result.changes), { status: 200 });
}

// UPDATE
export async function PUT({ params, request, locals, url }) {
  let user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in to make changes.' }, 401);
  }
  if (!user.verified) {
    return getResponse({ error: 'You must verify your account before making changes.' }, 403);
  }

  if (!params.slug) {
    return getResponse({ error: 'Please provide the change id.' }, 400);
  }

  let change = await getChangeById(params.slug);

  if (!change) {
    return getResponse({ error: 'Change not found.' }, 404);
  }
  if (change.author_id !== user.id && !user?.grants?.includes('admin.panel')) {
    return getResponse({ error: 'You are not the author of this change.' }, 403);
  }

  if (change.state !== 'Draft' && change.state !== 'Pending') {
    return getResponse({ error: 'This change was already finalized. You cannot edit it anymore. Please create a new change.' }, 400);
  }

  let entity = change.entity;

  // Enhancers are generated in the database and cannot be edited
  if (entity === 'Enhancer') {
    return getResponse({ error: 'Enhancers are generated in the database and cannot be edited.' }, 403);
  }
  let body = await request.json();
  let state = url.searchParams.get('state') || change.state;

  if (!body && !state) {
    return getResponse({ error: 'Please provide the body or the state.' }, 400);
  }

  if (body) {
    // Sanitize HTML in Description field to prevent XSS
    sanitizeBody(body);

    let errorResponse = validateChange(body, entity);
    if (errorResponse) {
      return errorResponse;
    }
  }
  else {
    body = change.data;
  }

  if (state !== 'Draft' && state !== 'Pending') {
    return getResponse({ error: 'Invalid state. Must be one of the following values: Draft, Pending' }, 400);
  }

  await updateChange(params.slug, body, state);

  return getResponse(204);
}

// CREATE
export async function POST({ request, params, locals, url }) {
  let user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in to make changes.' }, 401);
  }
  if (!user.verified) {
    return getResponse({ error: 'You must verify your account before making changes.' }, 403);
  }

  if (params.slug) {
    return getResponse({ error: 'Invalid request. Please do not provide the change id.' }, 400);
  }

  let entity = resolveEntityName(url.searchParams.get('entity'));
  let type = url.searchParams.get('type');

  if (!entity || !type) {
    return getResponse({ error: 'Please provide the entity and type.' }, 400);
  }
  if (!(await getChangeTypes()).includes(type)) {
    return getResponse({ error: `Invalid type. Must be one of the following values: ${(await getChangeTypes()).join(', ')}` }, 400);
  }
  if (!(await getChangeEntities()).includes(entity)) {
    return getResponse({ error: `Invalid entity. Must be one of the following values: ${(await getChangeEntities()).join(', ')}` }, 400);
  }

  // Enhancers are generated in the database and cannot be edited
  if (entity === 'Enhancer') {
    return getResponse({ error: 'Enhancers are generated in the database and cannot be edited.' }, 403);
  }

  let body = await request.json();

  // Sanitize HTML in Description field to prevent XSS
  sanitizeBody(body);

  let errorResponse = validateChange(body, entity);
  if (errorResponse) {
    return errorResponse;
  }

  if (type === 'Create') {
    if (body.Id) {
      return getResponse({ error: 'Cannot create an entity with a set Id.' }, 400);
    }

    errorResponse = await checkDuplicates(body.Name, entity);
    if (errorResponse) {
      return errorResponse;
    }
  }
  else if (type === 'Update') {
    const entityId = body?.Id ?? body?.ItemId;
    if (!entityId) {
      return getResponse({ error: 'Update changes require a valid entity Id.' }, 400);
    }
    const existingOpenChange = await getOpenChangeByEntityId(entity, entityId, 'Update');
    if (existingOpenChange) {
      return getResponse(
        {
          error: 'There is already an open update change for this entity.',
          existingChangeId: existingOpenChange.id
        },
        409
      );
    }
  }

  let state = url.searchParams.get('state') || 'Draft';

  if (state !== 'Draft' && state !== 'Pending') {
    return getResponse({ error: 'Invalid state. Must be one of the following values: Draft, Pending' }, 400);
  }

  return await createChange(user.id, type, state, entity, body)
    .then(x => getResponse(x, 201))
    .catch((error) => getResponse({ error: error.message }, 500));
}

// DELETE
export async function DELETE({ params, locals }) {
  let user = locals.session?.user;

  if (!user) {
    return getResponse({ error: 'You must be logged in to make changes.' }, 401);
  }
  if (!user.verified) {
    return getResponse({ error: 'You must verify your account before making changes.' }, 403);
  }

  if (!params.slug) {
    return getResponse({ error: 'Please provide the change id.' }, 400);
  }

  let change = await getChangeById(params.slug);

  if (!change) {
    return getResponse({ error: 'Change not found.' }, 404);
  }

  if (change.author_id !== user.id && !user?.grants?.includes('admin.panel')) {
    return getResponse({ error: 'You are not the author of this change.' }, 403);
  }

  if (change.state !== 'Draft' && change.state !== 'Pending') {
    return getResponse({ error: 'This change was already finalized. You cannot delete it anymore.' }, 400);
  }

  await deleteChange(params.slug);

  return new Response(null, { status: 204 });
}

function validateChange(body, entity) {
  if (!body) {
    return getResponse({ error: 'Body is empty.' }, 400);
  }

  // Use removeAdditional: true (not 'all') to preserve nested properties when additionalProperties: true
  // 'all' removes properties even when additionalProperties: true, which breaks Payload fields
  let validator = getValidator(entity, true);
  let valid = validator(body);

  if (!valid) {
    const details = (validator.errors || []).map(err => {
      const instancePath = (err.instancePath || '').replace(/^\//, '').replace(/\//g, '.');
      const missing = err.params?.missingProperty;
      const path = missing ? (instancePath ? `${instancePath}.${missing}` : missing) : instancePath;
      const message = err.message || 'Validation error';
      return {
        path,
        message,
        keyword: err.keyword
      };
    });
    const summary = details.length
      ? details.map(d => (d.path ? `${d.path}: ${d.message}` : d.message)).join('; ')
      : validator.errors.map(x => x.message).join(', ');
    return getResponse({ error: `Validation error: ${summary}`, details }, 400);
  }
}

async function checkDuplicates(name, entity) {
  const [apiEntity, dbEntities] = await Promise.all([
    apiCall(fetch, `/${getEntityCategory(entity)}/${encodeURIComponent(name)}`),
    executeVector(`SELECT entity FROM changes WHERE state IN ('Draft', 'Pending') AND data->>'Name' = $1`, [name])
  ]);

  if (apiEntity) {
    return getResponse({ error: `An "${entity}" with that name already exists.` }, 400);
  }
  if (dbEntities.some(x => getEntityCategory(x.entity) === getEntityCategory(entity))) {
    return getResponse({ error: `There is an open change of the same entity type with the same name.` }, 400);
  }
}

function getEntityCategory(entity) {
  if (entity === 'Mob') {
    return 'mobs';
  }
  else if (entity === 'Vendor') {
    return 'vendors';
  }
  else if (entity === 'Location') {
    return 'locations';
  }
  else if (entity === 'Area') {
    return 'areas';
  }
  else if (entity === 'ArmorSet') {
    return 'armorsets';
  }
  else if (entity === 'Shop') {
    return 'shops';
  }
  else if (entity === 'Profession') {
    return 'professions';
  }
  else if (entity === 'Skill') {
    return 'skills';
  }
  else if (entity === 'Strongbox') {
    return 'strongboxes';
  }
  else if (entity === 'Apartment') {
    return 'locations';
  }
  else if (entity === 'Mission') {
    return 'missions';
  }
  else {
    return 'items';
  }
}
