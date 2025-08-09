//@ts-nocheck
import { getChangeById, getChangeEntities as dbGetChangeEntities, getChangeTypes as dbGetChangeTypes, updateChange, deleteChange, createChange, executeVector, getChangeByEntityId } from "$lib/server/db.js"
import { apiCall, getResponse } from "$lib/util.js";
import Ajv from "ajv";
import { EffectsOnEquip, EffectsOnSetEquip, EffectsOnUse, NamedEntity, Tiers } from "$lib/common/schemas/SharedSchemas.js";

import { EntitySchemas } from "$lib/common/EntitySchemas.js";

const Validators = {}

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
  if (!params.slug && !url.searchParams.get('entityId')) {
    return getResponse({ error: 'Please provide the change id or entity id.' }, 400);
  }

  let change = url.searchParams.get('entityId')
    ? await getChangeByEntityId(url.searchParams.get('entityId'))
    : await getChangeById(params.slug);

  if (!change) {
    return getResponse({ error: 'Change not found.' }, 404);
  }

  return new Response(
    JSON.stringify(change),
    { status: 200 });
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
  let body = await request.json();
  let state = url.searchParams.get('state') || change.state;

  if (!body && !state) {
    return getResponse({ error: 'Please provide the body or the state.' }, 400);
  }

  if (body) {
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

  let body = await request.json();

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
  else if (entity === 'ArmorSet') {
    return 'armorsets';
  }
  else if (entity === 'Shop') {
    return 'shops';
  }
  else {
    return 'items';
  }
}