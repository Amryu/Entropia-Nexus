//@ts-nocheck
import { getChangeById, getChangeEntities as dbGetChangeEntities, getChangeTypes as dbGetChangeTypes, updateChange, deleteChange, createChange, executeVector, getChangeByEntityId, getChangesFiltered } from "$lib/server/db.js"
import { apiCall, getResponse } from "$lib/util.js";
import Ajv from "ajv";
import sanitizeHtml from "sanitize-html";
import { EffectsOnEquip, EffectsOnSetEquip, EffectsOnUse, NamedEntity, Tiers } from "$lib/common/schemas/SharedSchemas.js";

import { EntitySchemas } from "$lib/common/EntitySchemas.js";

const Validators = {}

// HTML sanitization config for TipTap rich text editor output
const SANITIZE_CONFIG = {
  allowedTags: [
    // Basic formatting
    'p', 'strong', 'em', 's', 'code', 'br',
    // Headings
    'h1', 'h2', 'h3', 'h4',
    // Lists
    'ul', 'ol', 'li',
    // Block elements
    'blockquote', 'pre', 'hr',
    // Links
    'a',
    // Video embeds (custom TipTap extension)
    'div', 'iframe'
  ],
  allowedAttributes: {
    'a': ['href', 'target', 'rel'],
    'div': ['data-type', 'data-provider', 'data-src', 'class'],
    'iframe': ['src', 'width', 'height', 'frameborder', 'allow', 'allowfullscreen']
  },
  allowedIframeHostnames: ['www.youtube.com', 'youtube.com', 'player.vimeo.com', 'vimeo.com'],
  // Force safe link attributes
  transformTags: {
    'a': (tagName, attribs) => {
      return {
        tagName: 'a',
        attribs: {
          href: attribs.href || '',
          target: '_blank',
          rel: 'noopener noreferrer'
        }
      };
    }
  }
};

/**
 * Sanitizes the Description field if present in the body.
 * This prevents XSS attacks from forged requests bypassing the frontend.
 */
function sanitizeBody(body) {
  if (body && typeof body.Description === 'string') {
    body.Description = sanitizeHtml(body.Description, SANITIZE_CONFIG);
  }
  if (body?.Properties && typeof body.Properties.Description === 'string') {
    body.Properties.Description = sanitizeHtml(body.Properties.Description, SANITIZE_CONFIG);
  }
  return body;
}

let change_entities = null;
let change_types = null;

let shared = [EffectsOnEquip, EffectsOnSetEquip, EffectsOnUse, NamedEntity, Tiers];

function getValidator(type) {
  if (!Validators[type]) {
    Validators[type] = new Ajv({ schemas: shared, strict: false, removeAdditional: 'all', useDefaults: true }).compile(EntitySchemas[type]);
  }

  return Validators[type];
}

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

  // Parse entity filter
  const entity = url.searchParams.get('entity');
  if (entity) {
    const validEntities = await getChangeEntities();
    const entityList = entity.split(',').map(e => e.trim()).filter(Boolean);
    const invalidEntities = entityList.filter(e => !validEntities.includes(e));
    if (invalidEntities.length > 0) {
      return getResponse({ error: `Invalid entity. Must be one of: ${validEntities.join(', ')}` }, 400);
    }
    filters.entity = entity;
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
  if (change.author_id !== user.id && !user.administrator) {
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

  let entity = url.searchParams.get('entity');
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

  if (change.author_id !== user.id && !user.administrator) {
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

  let validator = getValidator(entity);
  let valid = validator(body);

  if (!valid) {
    return getResponse({ error: 'Validation error: ' + validator.errors.map(x => x.message).join(', ') }, 400);
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
  else {
    return 'items';
  }
}
