<!--
  @component InlineEdit
  Inline editable field component that switches between view and edit modes.
  Supports various field types: text, number, select, checkbox, coordinates, etc.
-->
<script>
  // @ts-nocheck
  import {
    editMode,
    updateField,
    setFieldError,
    validationErrors,
    getNestedValue
  } from '$lib/stores/wikiEditState.js';

  

  

  

  

  

  

  

  

  

  

  

  

  

  

  
  /**
   * @typedef {Object} Props
   * @property {any} [value]
   * @property {string} [path]
   * @property {string} [type]
   * @property {string} [datalistId]
   * @property {string} [prefix]
   * @property {string} [suffix]
   * @property {string} [placeholder]
   * @property {Array} Options for select type [{value, label} [options]
   * @property {Function|null} [validate]
   * @property {number|null} [min]
   * @property {number|null} [max]
   * @property {number|null} [step]
   * @property {boolean} [required]
   * @property {string} [displayFormat]
   * @property {boolean} [editable]
   * @property {Function} [onchange]
   */

  /** @type {Props} */
  let {
    value = '',
    path = '',
    type = 'text',
    datalistId = '',
    prefix = '',
    suffix = '',
    placeholder = '',
    options = [],
    validate = null,
    min = null,
    max = null,
    step = null,
    required = false,
    displayFormat = '',
    editable = undefined,
    onchange
  } = $props();

  // Internal state
  let inputEl = $state();
  let localValue = $state(value);
  let error = $state(null);

  // Determine if field is editable
  let isEditable = $derived(editable !== undefined ? editable : $editMode);

  // Sync local value with prop
  $effect(() => {
    localValue = value;
  });

  // Get error from store
  $effect(() => {
    error = path ? $validationErrors[path] : null;
  });

  function handleInput(event) {
    let newValue = event.target.value;

    // Strip game client brackets from Name fields: [Item Name] → Item Name
    if (path === 'Name' && type === 'text') {
      const stripped = newValue.replace(/^\[+|\]+$/g, '');
      if (stripped !== newValue) {
        newValue = stripped;
        event.target.value = stripped;
      }
    }

    // Type coercion
    if (type === 'number') {
      newValue = newValue === '' ? null : parseFloat(newValue);
    } else if (type === 'select') {
      newValue = newValue === '' ? null : newValue;
    } else if (type === 'checkbox') {
      newValue = event.target.checked;
    }

    localValue = newValue;
    validateAndUpdate(newValue);
  }

  function handleBlur() {
    validateAndUpdate(localValue);
  }

  function validateAndUpdate(newValue) {
    // Clear previous error
    if (path) {
      setFieldError(path, null);
    }

    // Required validation
    if (required && (newValue === '' || newValue === null || newValue === undefined)) {
      const errorMsg = 'This field is required';
      if (path) {
        setFieldError(path, errorMsg);
      }
      error = errorMsg;
      return;
    }

    // Number range validation
    if (type === 'number' && newValue !== null) {
      if (min !== null && newValue < min) {
        const errorMsg = `Value must be at least ${min}`;
        if (path) {
          setFieldError(path, errorMsg);
        }
        error = errorMsg;
        return;
      }
      if (max !== null && newValue > max) {
        const errorMsg = `Value must be at most ${max}`;
        if (path) {
          setFieldError(path, errorMsg);
        }
        error = errorMsg;
        return;
      }
    }

    // Custom validation
    if (validate) {
      const customError = validate(newValue);
      if (customError) {
        if (path) {
          setFieldError(path, customError);
        }
        error = customError;
        return;
      }
    }

    // Update store
    if (path) {
      updateField(path, newValue);
    }

    // Dispatch change event
    onchange?.({ value: newValue, path });
  }

  function formatDisplayValue(val) {
    if (val === null || val === undefined || val === '') {
      return placeholder || '—';
    }

    if (type === 'checkbox') {
      return val ? 'Yes' : 'No';
    }

    if (type === 'select') {
      const option = options.find(o => o.value === val);
      return option ? option.label : val;
    }

    if (type === 'number' && displayFormat) {
      return displayFormat.replace('{value}', val);
    }

    return val;
  }
</script>

<span class="inline-edit" class:editable={isEditable} class:has-error={error}>
  {#if isEditable}
    <span class="edit-wrapper">
      {#if prefix}
        <span class="prefix">{prefix}</span>
      {/if}

      {#if type === 'text' || type === 'number'}
        <input
          bind:this={inputEl}
          type={type === 'number' ? 'number' : 'text'}
          value={localValue ?? ''}
          {placeholder}
          {min}
          {max}
          {step}
          class="edit-input"
          oninput={handleInput}
          onblur={handleBlur}
        />
      {:else if type === 'textarea'}
        <textarea
          bind:this={inputEl}
          value={localValue ?? ''}
          {placeholder}
          class="edit-textarea"
          oninput={handleInput}
          onblur={handleBlur}
          rows="3"
></textarea>
      {:else if type === 'select'}
        {#key options.length}
        <select
          bind:this={inputEl}
          value={localValue ?? ''}
          class="edit-select"
          onchange={handleInput}
        >
          <option value="">{placeholder || 'Select...'}</option>
          {#each options as option}
            <option value={option.value}>{option.label}</option>
          {/each}
        </select>
        {/key}
      {:else if type === 'autocomplete'}
        <input
          bind:this={inputEl}
          type="text"
          value={localValue ?? ''}
          {placeholder}
          class="edit-input edit-autocomplete"
          list={datalistId || `datalist-${path}`}
          oninput={handleInput}
          onblur={handleBlur}
        />
        <datalist id={datalistId || `datalist-${path}`}>
          {#each options as option}
            <option value={option.value}>{option.label}</option>
          {/each}
        </datalist>
      {:else if type === 'checkbox'}
        <input
          bind:this={inputEl}
          type="checkbox"
          checked={localValue ?? false}
          class="edit-checkbox"
          onchange={handleInput}
        />
      {:else if type === 'coordinates'}
        <span class="coordinates-input">
          <input
            type="number"
            value={localValue?.x ?? ''}
            placeholder="X"
            class="edit-input coord"
            oninput={(e) => {
              localValue = { ...localValue, x: parseFloat(e.target.value) || 0 };
              validateAndUpdate(localValue);
            }}
          />
          <span class="coord-separator">,</span>
          <input
            type="number"
            value={localValue?.y ?? ''}
            placeholder="Y"
            class="edit-input coord"
            oninput={(e) => {
              localValue = { ...localValue, y: parseFloat(e.target.value) || 0 };
              validateAndUpdate(localValue);
            }}
          />
        </span>
      {/if}

      {#if suffix}
        <span class="suffix">{suffix}</span>
      {/if}
    </span>

    {#if error}
      <span class="error-message">{error}</span>
    {/if}
  {:else}
    <span class="display-value">
      {#if prefix}
        <span class="prefix">{prefix}</span>
      {/if}
      <span class="value">{formatDisplayValue(value)}</span>
      {#if suffix && value !== null && value !== undefined && value !== ''}
        <span class="suffix">{suffix}</span>
      {/if}
    </span>
  {/if}
</span>

<style>
  .inline-edit {
    display: inline-flex;
    flex-direction: column;
    gap: 2px;
  }

  .edit-wrapper {
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }

  .display-value {
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }

  .prefix,
  .suffix {
    color: var(--text-muted, #999);
    font-size: 0.9em;
  }

  .value {
    color: var(--text-color);
  }

  .edit-input,
  .edit-textarea,
  .edit-select {
    padding: 4px 8px;
    border: 1px solid var(--border-color, #555);
    border-radius: 4px;
    background-color: var(--bg-color, var(--primary-color));
    color: var(--text-color);
    font-size: inherit;
    font-family: inherit;
  }

  .edit-input {
    width: auto;
    min-width: 60px;
  }

  .edit-input[type="number"] {
    width: 80px;
  }

  .edit-textarea {
    width: 100%;
    min-width: 200px;
    resize: vertical;
  }

  .edit-select {
    min-width: 100px;
  }

  .edit-input:focus,
  .edit-textarea:focus,
  .edit-select:focus {
    outline: none;
    border-color: var(--accent-color, #4a9eff);
  }

  .has-error .edit-input,
  .has-error .edit-textarea,
  .has-error .edit-select {
    border-color: var(--error-color, #ff6b6b);
  }

  .edit-checkbox {
    width: 18px;
    height: 18px;
    cursor: pointer;
  }

  .coordinates-input {
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }

  .coord {
    width: 70px;
  }

  .coord-separator {
    color: var(--text-muted, #999);
  }

  .error-message {
    font-size: 12px;
    color: var(--error-color, #ff6b6b);
  }

  /* Editable styling hint */
  .inline-edit.editable .edit-input,
  .inline-edit.editable .edit-textarea,
  .inline-edit.editable .edit-select {
    background-color: var(--bg-secondary, var(--secondary-color));
  }

  /* Mobile adjustments - aligned with global 900px breakpoint */
  @media (max-width: 899px) {
    .edit-input,
    .edit-textarea,
    .edit-select {
      padding: 6px 8px;
    }
  }
</style>
