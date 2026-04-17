// @ts-nocheck
import { writable, derived } from 'svelte/store';

/**
 * Wiki Edit State Store
 * Manages edit mode, pending changes, and validation state for wiki pages.
 */

// Edit mode: true when user is editing, false when viewing
export const editMode = writable(false);

// Create mode: true when creating a new entity (cannot exit edit mode, cancel navigates back)
export const isCreateMode = writable(false);

// The original entity data (before any edits)
export const originalEntity = writable(null);

// Pending changes - tracks all field modifications
// Structure: { fieldPath: newValue, ... }
// e.g., { 'Properties.Weight': 3.5, 'Name': 'New Name' }
const pendingChanges = writable({});

// Validation errors - tracks field-level errors
// Structure: { fieldPath: errorMessage, ... }
export const validationErrors = writable({});

// Field-level warnings (non-blocking, unlike validationErrors)
// Used for similarity checks and other advisory messages
export const fieldWarnings = writable({});

// Change metadata (for API submission)
export const changeMetadata = writable({
  id: null,
  state: 'Draft', // Draft, Pending, Approved, Rejected
  type: 'Update', // Create, Update, Delete
  entity: null,
  author_id: null,
  content_updated_at: null // optimistic locking token
});

// === Pending Change Viewing ===
// Stores the pending change object from the API (if any exists)
export const existingPendingChange = writable(null);

// Whether to view the pending change version vs original
export const viewingPendingChange = writable(false);

// Derived: Check if there are any unsaved changes
export const hasChanges = derived(pendingChanges, ($changes) => {
  return Object.keys($changes).length > 0;
});

// Derived: Check if there are any validation errors
export const hasErrors = derived(validationErrors, ($errors) => {
  return Object.keys($errors).length > 0;
});

// Derived: Check if there are any field warnings
export const hasWarnings = derived(fieldWarnings, ($warnings) => {
  return Object.keys($warnings).length > 0;
});

const NAMED_ENTITY_PATHS = {
  Apartment: ['Planet'],
  Area: ['Planet'],
  Location: ['Planet', 'ParentLocation', 'Facilities[]'],
  Shop: ['Planet', 'Owner'],
  Vendor: ['Planet', 'Offers[].Item', 'Offers[].Prices[].Item'],
  Pet: ['Planet'],
  Mob: [
    'Planet',
    'DefensiveProfession',
    'Species',
    'Loots[].Maturity',
    'Loots[].Item',
    'Spawns[].Maturities[].Maturity.Mob'
  ],
  Mission: ['Planet', 'MissionChain'],
  MissionChain: ['Planet'],
  Capsule: ['Profession', 'Mob'],
  EffectChip: ['Ammo', 'Profession'],
  MedicalChip: ['Ammo'],
  TeleportationChip: ['Ammo', 'Profession'],
  MiscTool: ['Profession'],
  Weapon: ['Ammo', 'AttachmentType', 'ProfessionHit', 'ProfessionDmg'],
  Vehicle: ['Fuel', 'AttachmentSlots[]'],
  Blueprint: ['Book', 'Product', 'Profession'],
  Material: ['RefiningRecipes[].Ingredients[].Item'],
  Strongbox: ['Loots[].Item'],
  Skill: ['Category', 'Professions[].Profession', 'Unlocks[].Profession'],
  Profession: ['Category', 'Skills[].Skill', 'Unlocks[].Skill'],
  Fish: ['Species', 'FishOil', 'Planets[]']
};

function normalizeNamedEntity(value) {
  if (value === null || value === undefined) {
    return { Name: null };
  }
  if (typeof value === 'string') {
    return { Name: value };
  }
  if (typeof value !== 'object') {
    return { Name: null };
  }
  if (!('Name' in value)) {
    return { ...value, Name: null };
  }
  if (value.Name === undefined) {
    return { ...value, Name: null };
  }
  return value;
}

function applyNamedEntityPath(target, parts) {
  if (!target || parts.length === 0) return;

  const rawPart = parts[0];
  const isArray = rawPart.endsWith('[]');
  const key = isArray ? rawPart.slice(0, -2) : rawPart;

  if (parts.length === 1) {
    if (isArray) {
      const arr = target[key];
      if (Array.isArray(arr)) {
        for (let i = 0; i < arr.length; i++) {
          arr[i] = normalizeNamedEntity(arr[i]);
        }
      }
      return;
    }
    target[key] = normalizeNamedEntity(target[key]);
    return;
  }

  if (isArray) {
    const arr = target[key];
    if (Array.isArray(arr)) {
      for (const item of arr) {
        applyNamedEntityPath(item, parts.slice(1));
      }
    }
    return;
  }

  if (target[key] === null || target[key] === undefined || typeof target[key] !== 'object') {
    target[key] = {};
  }
  applyNamedEntityPath(target[key], parts.slice(1));
}

function normalizeEntityForSchema(entityType, entity) {
  if (!entity || !entityType) return entity;
  const paths = NAMED_ENTITY_PATHS[entityType];
  if (!paths || paths.length === 0) return entity;

  const normalized = JSON.parse(JSON.stringify(entity));
  for (const path of paths) {
    applyNamedEntityPath(normalized, path.split('.'));
  }
  return normalized;
}

// Derived: Get the current entity with pending changes applied
export const currentEntity = derived(
  [originalEntity, pendingChanges],
  ([$original, $changes]) => {
    if (!$original) return null;

    // Deep clone the original
    const current = JSON.parse(JSON.stringify($original));

    // Apply pending changes
    for (const [path, value] of Object.entries($changes)) {
      setNestedValue(current, path, value);
    }

    return current;
  }
);

/**
 * Set a nested value in an object using dot notation path
 * @param {object} obj - The object to modify
 * @param {string} path - Dot notation path (e.g., 'Properties.Weight')
 * @param {any} value - The value to set
 */
function setNestedValue(obj, path, value) {
  const parts = path.split('.');
  let current = obj;

  for (let i = 0; i < parts.length - 1; i++) {
    const part = parts[i];
    // Check for both undefined and null - create object if needed
    if (current[part] === undefined || current[part] === null) {
      current[part] = {};
    }
    current = current[part];
  }

  current[parts[parts.length - 1]] = value;
}

/**
 * Get a nested value from an object using dot notation path
 * @param {object} obj - The object to read from
 * @param {string} path - Dot notation path (e.g., 'Properties.Weight')
 * @returns {any} The value at the path, or undefined if not found
 */
export function getNestedValue(obj, path) {
  if (!obj || !path) return undefined;

  const parts = path.split('.');
  let current = obj;

  for (const part of parts) {
    if (current === undefined || current === null) return undefined;
    current = current[part];
  }

  return current;
}

/**
 * Initialize the edit state with an entity
 * @param {object} entity - The entity to edit (null for create mode)
 * @param {string} entityType - The type of entity (e.g., 'Weapon', 'Mob')
 * @param {boolean} createMode - Whether this is create mode (new entity)
 * @param {object|null} existingChange - An existing pending change to edit (if any)
 */
function buildEntityFromChange(entity, change) {
  if (!change) return entity;
  if (change.data) {
    return change.data;
  }
  if (change.changes && entity) {
    const merged = JSON.parse(JSON.stringify(entity));
    for (const [path, value] of Object.entries(change.changes)) {
      setNestedValue(merged, path, value);
    }
    return merged;
  }
  return entity;
}

export function initEditState(entity, entityType, createMode = false, existingChange = null) {
  const resolvedEntity = normalizeEntityForSchema(
    entityType,
    buildEntityFromChange(entity, existingChange)
  );
  originalEntity.set(resolvedEntity);
  pendingChanges.set({});
  validationErrors.set({});
  isCreateMode.set(createMode);

  // Set metadata from existing change or create new
  changeMetadata.set({
    id: existingChange?.id || null,
    state: existingChange?.state || 'Draft',
    type: createMode ? 'Create' : 'Update',
    entity: entityType,
    author_id: existingChange?.author_id || null,
    content_updated_at: existingChange?.content_updated_at || null
  });

  // Auto-start edit mode in create mode
  if (createMode) {
    editMode.set(true);
  }
}

/**
 * Update a field value
 * @param {string} path - Dot notation path to the field
 * @param {any} value - The new value
 */
export function updateField(path, value) {
  pendingChanges.update(changes => {
    // Check if the value is the same as original
    let original;
    originalEntity.subscribe(e => original = e)();
    const originalValue = getNestedValue(original, path);

    if (JSON.stringify(value) === JSON.stringify(originalValue)) {
      // Value is same as original, remove from pending changes
      const { [path]: _, ...rest } = changes;
      return rest;
    }

    return { ...changes, [path]: value };
  });
}

/**
 * Set a validation error for a field
 * @param {string} path - Dot notation path to the field
 * @param {string|null} error - The error message, or null to clear
 */
export function setFieldError(path, error) {
  validationErrors.update(errors => {
    if (error === null) {
      const { [path]: _, ...rest } = errors;
      return rest;
    }
    return { ...errors, [path]: error };
  });
}

/**
 * Set a non-blocking warning for a field (e.g. similar name detected)
 * @param {string} path - Dot notation path to the field
 * @param {string|null} warning - The warning message, or null to clear
 */
export function setFieldWarning(path, warning) {
  fieldWarnings.update(warnings => {
    if (warning === null) {
      const { [path]: _, ...rest } = warnings;
      return rest;
    }
    return { ...warnings, [path]: warning };
  });
}

/**
 * Mark changes as saved — rebase originalEntity to include pending changes and clear dirty state.
 * Called after a successful save (Draft, DirectApply, etc.) so the form reflects the persisted state.
 */
export function markSaved() {
  let current;
  currentEntity.subscribe(e => current = e)();
  if (current) {
    originalEntity.set(JSON.parse(JSON.stringify(current)));
  }
  pendingChanges.set({});
  validationErrors.set({});
}

/**
 * Clear all pending changes and exit edit mode.
 * Also resets create mode — otherwise afterNavigate re-enters edit mode on cancel.
 */
export function cancelEdit() {
  editMode.set(false);
  isCreateMode.set(false);
  pendingChanges.set({});
  validationErrors.set({});
  fieldWarnings.set({});
  viewingPendingChange.set(false);
}

// Flag consumed by WikiPage's beforeNavigate to skip the "unsaved changes" prompt
// for programmatic navigations triggered by save/submit/direct-apply flows.
let _skipNextNavGuard = false;
export function suppressNextNavGuard() {
  _skipNextNavGuard = true;
}
export function consumeNavGuardSuppression() {
  const flag = _skipNextNavGuard;
  _skipNextNavGuard = false;
  return flag;
}

/**
 * Enter edit mode
 */
export function startEdit() {
  editMode.set(true);
}

/**
 * Reset all edit state
 */
export function resetEditState() {
  editMode.set(false);
  isCreateMode.set(false);
  originalEntity.set(null);
  pendingChanges.set({});
  validationErrors.set({});
  fieldWarnings.set({});
  changeMetadata.set({
    id: null,
    state: 'Draft',
    type: 'Update',
    entity: null,
    author_id: null,
    content_updated_at: null
  });
  existingPendingChange.set(null);
  viewingPendingChange.set(false);
}

/**
 * Get the change object ready for API submission
 * @returns {object} The change object
 */
export function getChangeForSubmission() {
  let metadata, original, changes;
  changeMetadata.subscribe(m => metadata = m)();
  originalEntity.subscribe(e => original = e)();
  pendingChanges.subscribe(c => changes = c)();

  // Build the modified entity
  const data = JSON.parse(JSON.stringify(original || {}));
  for (const [path, value] of Object.entries(changes)) {
    setNestedValue(data, path, value);
  }

  const normalizedData = normalizeEntityForSchema(metadata?.entity, data);

  return {
    ...metadata,
    data: normalizedData,
    entityId: original?.Id || null
  };
}

/**
 * Set the existing pending change (from API)
 * @param {object|null} change - The pending change object or null
 */
export function setExistingPendingChange(change) {
  existingPendingChange.set(change);
  // If user is the author or an admin, auto-enable viewing pending change
  // This is handled in the page component based on user permissions
}

/**
 * Set whether to view the pending change
 * @param {boolean} viewing - True to view pending change, false for original
 */
export function setViewingPendingChange(viewing) {
  viewingPendingChange.set(viewing);
}

