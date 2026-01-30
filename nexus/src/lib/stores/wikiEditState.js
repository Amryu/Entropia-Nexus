// @ts-nocheck
import { writable, derived } from 'svelte/store';

/**
 * Wiki Edit State Store
 * Manages edit mode, pending changes, and validation state for wiki pages.
 */

// Edit mode: true when user is editing, false when viewing
export const editMode = writable(false);

// The original entity data (before any edits)
export const originalEntity = writable(null);

// Pending changes - tracks all field modifications
// Structure: { fieldPath: newValue, ... }
// e.g., { 'Properties.Weight': 3.5, 'Name': 'New Name' }
export const pendingChanges = writable({});

// Validation errors - tracks field-level errors
// Structure: { fieldPath: errorMessage, ... }
export const validationErrors = writable({});

// Change metadata (for API submission)
export const changeMetadata = writable({
  id: null,
  state: 'Draft', // Draft, Pending, Approved, Rejected
  type: 'Update', // Create, Update, Delete
  entity: null,
  author_id: null
});

// Derived: Check if there are any unsaved changes
export const hasChanges = derived(pendingChanges, ($changes) => {
  return Object.keys($changes).length > 0;
});

// Derived: Check if there are any validation errors
export const hasErrors = derived(validationErrors, ($errors) => {
  return Object.keys($errors).length > 0;
});

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
    if (current[part] === undefined) {
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
 * @param {object} entity - The entity to edit
 * @param {string} entityType - The type of entity (e.g., 'weapon', 'mob')
 * @param {number} userId - The current user's ID
 */
export function initEditState(entity, entityType, userId) {
  originalEntity.set(entity);
  pendingChanges.set({});
  validationErrors.set({});
  changeMetadata.set({
    id: null,
    state: 'Draft',
    type: entity ? 'Update' : 'Create',
    entity: entityType,
    author_id: userId
  });
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
 * Clear all pending changes and exit edit mode
 */
export function cancelEdit() {
  editMode.set(false);
  pendingChanges.set({});
  validationErrors.set({});
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
  originalEntity.set(null);
  pendingChanges.set({});
  validationErrors.set({});
  changeMetadata.set({
    id: null,
    state: 'Draft',
    type: 'Update',
    entity: null,
    author_id: null
  });
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

  return {
    ...metadata,
    data,
    entityId: original?.Id || null
  };
}
